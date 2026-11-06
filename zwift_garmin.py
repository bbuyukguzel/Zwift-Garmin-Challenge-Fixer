"""Convert a Zwift ride locally and optionally upload it to Garmin Connect."""

import argparse
from getpass import getpass
import io
import json
import os
from pathlib import Path
import struct

import fitdecode
from fitdecode.utils import compute_crc


GARMIN, ZWIFT, TACX_WINDOWS = 1, 260, 20533
EDGE_1050 = 4440
FENIX_8 = 4536
CYCLING, INDOOR_CYCLING = 2, 6
SPORT_FIELDS = {"sport": (0, 1), "session": (5, 6), "lap": (25, 39)}


def read_fit(data):
    if (
        len(data) < 14
        or data[0] not in (12, 14)
        or data[8:12] != b".FIT"
        or data[0] + struct.unpack_from("<I", data, 4)[0] + 2 != len(data)
    ):
        raise ValueError("Expected one complete FIT file.")
    with fitdecode.FitReader(
        io.BytesIO(data), keep_raw_chunks=True,
        check_crc=fitdecode.CrcCheck.RAISE,
        error_handling=fitdecode.ErrorHandling.RAISE,
    ) as reader:
        yield from (frame for frame in reader if isinstance(frame, fitdecode.FitDataMessage))


def raw(message, number):
    return message.get_raw_value(number, fallback=None)


def patch_fields(data, message, replacements, required=()):
    offset = message.chunk.offset + 1
    written = set()
    for field in message.def_mesg.field_defs:
        if field.def_num in replacements:
            value, size = replacements[field.def_num]
            if size is None:
                if field.base_type.name != "string":
                    raise ValueError(f"Unexpected product name type in {message.name}.")
                encoded = bytes(field.size)
            else:
                if field.size != size:
                    raise ValueError(f"Unexpected field size in {message.name}: {field.def_num}")
                byte_order = "little" if message.def_mesg.endian == "<" else "big"
                encoded = value.to_bytes(size, byte_order)
            data[offset:offset + field.size] = encoded
            written.add(field.def_num)
        offset += field.size
    if set(required) - written:
        raise ValueError(f"Required fields missing from {message.name}.")


def convert(source, indoor=False, reference=None, *, product=TACX_WINDOWS):
    unit_id = 0
    if reference is not None:
        identities = [m for m in read_fit(reference) if m.name == "file_id"]
        if len(identities) != 1:
            raise ValueError("Expected one device identity in the Garmin reference.")
        identity = identities[0]
        product, unit_id = raw(identity, 2), raw(identity, 3)
        if raw(identity, 0) != 4 or raw(identity, 1) != GARMIN or not product or not unit_id:
            raise ValueError("Reference must be a Garmin-recorded activity with a product and Unit ID.")

    result = bytearray(source)
    files = sessions = 0
    for message in read_fit(source):
        if message.name == "file_id":
            if raw(message, 0) != 4 or raw(message, 1) != ZWIFT:
                raise ValueError("Input must be a Zwift activity.")
            patch_fields(result, message, {
                1: (GARMIN, 2), 2: (product, 2), 3: (unit_id, 4), 8: (None, None),
            }, required=(1, 2, 3) if reference is not None else (1, 2))
            files += 1
        elif message.name == "device_info" and raw(message, 0) == 0 and raw(message, 2) == ZWIFT:
            patch_fields(result, message, {
                2: (GARMIN, 2), 4: (product, 2), 3: (unit_id, 4), 27: (None, None),
            }, required=(2, 4))
        elif message.name in SPORT_FIELDS:
            sport, sub_sport = SPORT_FIELDS[message.name]
            if message.name == "session":
                if raw(message, sport) != CYCLING:
                    raise ValueError("Input must contain cycling sessions only.")
                sessions += 1
            if indoor and raw(message, sport) == CYCLING:
                required = (sub_sport,) if message.name == "session" else ()
                patch_fields(result, message, {sub_sport: (INDOOR_CYCLING, 1)}, required)

    if files != 1 or not sessions:
        raise ValueError("Expected one Zwift activity identity and at least one cycling session.")
    if result[0] == 14:
        struct.pack_into("<H", result, 12, compute_crc(result, end=12))
    struct.pack_into("<H", result, len(result) - 2, compute_crc(result, end=len(result) - 2))
    for _ in read_fit(result):
        pass
    return result


def garmin_environment():
    return os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"), os.getenv("GARMINTOKENS")


def require_garmin_environment():
    email, password, tokenstore = garmin_environment()
    if not tokenstore and not (email and password):
        raise RuntimeError("Set GARMINTOKENS or both GARMIN_EMAIL and GARMIN_PASSWORD.")


def upload(path, *, non_interactive=False):
    try:
        from garminconnect import Garmin
    except ImportError as exc:
        raise RuntimeError("Install the upload dependency with: python -m pip install garminconnect==0.3.20") from exc

    email, password, tokenstore = garmin_environment()
    if non_interactive:
        require_garmin_environment()
    elif not tokenstore:
        email = email or input("Garmin email: ").strip()
        password = password or getpass("Garmin password: ")
    client = Garmin(email=email, password=password, return_on_mfa=True)
    status, state = client.login(tokenstore)
    if status == "needs_mfa":
        if non_interactive:
            raise RuntimeError("Garmin requires MFA. Provide a valid saved session via GARMINTOKENS.")
        client.resume_login(state, getpass("Garmin MFA code: ").strip())
    response = client.upload_activity(str(path))
    print(json.dumps(response, ensure_ascii=False, indent=2))
    if not isinstance(response, dict) or not response.get("detailedImportResult", {}).get("successes"):
        raise RuntimeError("Garmin did not confirm a new import. Check Connect before retrying.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    converter = commands.add_parser("convert", help="Create a new FIT file")
    converter.add_argument("source", type=Path)
    converter.add_argument("-o", "--output", type=Path)
    latest = commands.add_parser("latest", help="Download and convert your latest Zwift ride")
    for command in (converter, latest):
        command.add_argument("--indoor", action="store_true")
        device = command.add_mutually_exclusive_group()
        device.add_argument("--edge-1050", dest="product", action="store_const", const=EDGE_1050,
                            default=TACX_WINDOWS, help="Use the Edge 1050 product code")
        device.add_argument("--fenix-8", dest="product", action="store_const", const=FENIX_8,
                            help="Use the standard fenix 8 product code")
        device.add_argument("--garmin-reference", type=Path, help="FIT activity from your Garmin device")
        command.add_argument("--upload", action="store_true")
    uploader = commands.add_parser("upload", help="Upload an existing FIT file")
    uploader.add_argument("path", type=Path)
    for command in (converter, latest, uploader):
        command.add_argument("--non-interactive", action="store_true", help="Require credentials from the environment")
    args = parser.parse_args()

    try:
        if args.non_interactive and (args.command == "upload" or args.upload):
            require_garmin_environment()
        if args.command == "upload":
            if args.path.suffix.lower() != ".fit" or not args.path.is_file():
                raise ValueError("Provide an existing .fit file.")
            upload(args.path, non_interactive=args.non_interactive)
            return

        reference = args.garmin_reference.read_bytes() if args.garmin_reference else None
        if args.command == "latest":
            from zwift_remote import download_latest_ride

            activity_id, source = download_latest_ride(non_interactive=args.non_interactive)
            target = Path(f"zwift-{activity_id}.garmin.fit")
        else:
            source = args.source.read_bytes()
            target = args.output or args.source.with_name(f"{args.source.stem}.garmin.fit")
        if target.suffix.lower() != ".fit":
            raise ValueError("Output must have a .fit extension.")
        result = convert(source, args.indoor, reference, product=args.product)
        try:
            with target.open("xb") as file:
                file.write(result)
        except FileExistsError:
            if args.command != "latest" or target.read_bytes() != result:
                raise
            print(f"Already converted: {target.resolve()}")
            if args.upload:
                print("Use the upload command if this file has not been imported yet.")
            return
        print(target.resolve(), flush=True)
        if args.upload:
            upload(target, non_interactive=args.non_interactive)
    except Exception as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
