"""Read the latest completed ride from Zwift's private Companion API."""

from datetime import datetime, timezone
from getpass import getpass
import os
import re
from urllib.parse import quote


TOKEN_URL = "https://secure.zwift.com/auth/realms/zwift/protocol/openid-connect/token"
API_URL = "https://us-or-rly101.zwift.com"
HEADERS = {"User-Agent": "Zwift/115 CFNetwork/1335.0.3 Darwin/21.6.0"}
MAX_FIT_BYTES = 50 * 1024 * 1024


def checked(response, operation):
    if response.status_code != 200:
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code}).")
    return response


def activity_end(activity):
    value = activity["endDate"]
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else value
    date = datetime.fromisoformat(value)
    return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()


def numeric_id(value):
    value = str(value)
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Zwift returned an invalid ID.")
    return value


def download_latest_ride(*, non_interactive=False):
    import requests

    username = os.getenv("ZWIFT_USER")
    password = os.getenv("ZWIFT_PASSWORD")
    if non_interactive and (not username or not password):
        raise RuntimeError("Set ZWIFT_USER and ZWIFT_PASSWORD before running without prompts.")
    username = username or input("Zwift email: ").strip()
    password = password or getpass("Zwift password: ")
    with requests.Session() as session:
        token = checked(session.post(
            TOKEN_URL,
            data={"client_id": "Zwift_Mobile_Link", "grant_type": "password",
                  "username": username, "password": password},
            headers=HEADERS, timeout=30, allow_redirects=False,
        ), "Zwift login").json()["access_token"]
        auth = {**HEADERS, "Authorization": f"Bearer {token}", "Accept": "application/json"}

        def api(path, params=None):
            return checked(session.get(
                API_URL + path, params=params, headers=auth, timeout=30, allow_redirects=False,
            ), "Zwift API request").json()

        profile_id = numeric_id(api("/api/profiles/me")["id"])
        rides = []
        for start in range(0, 300, 30):
            activities = api(f"/api/profiles/{profile_id}/activities",
                             {"start": start, "limit": 30})
            if isinstance(activities, dict):
                activities = activities.get("activities") or activities.get("data") or []
            if not activities:
                break
            rides = [a for a in activities if a.get("endDate")
                     and str(a.get("sport")).upper() in {"CYCLING", "0"}]
            if rides:
                break
        if not rides:
            raise ValueError("No completed cycling activity found in the recent Zwift feed.")

        ride = max(rides, key=activity_end)
        activity_id = numeric_id(ride.get("id_str") or ride.get("id") or ride.get("activityId"))
        title = ride.get("name") or ride.get("activityName")
        if not ride.get("fitFileBucket") or not ride.get("fitFileKey"):
            ride = api(f"/api/activities/{activity_id}")
            title = title or ride.get("name") or ride.get("activityName")
        bucket, key = ride.get("fitFileBucket"), ride.get("fitFileKey")
        if not bucket or not key:
            raise RuntimeError(f"FIT for Zwift activity {activity_id} is unavailable. Try again after syncing.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
            raise ValueError("Zwift returned an invalid FIT storage bucket.")
        url = f"https://{bucket}.s3.amazonaws.com/{quote(key)}"
        with session.get(url, headers=HEADERS, timeout=60, stream=True, allow_redirects=False) as response:
            checked(response, "Zwift FIT download")
            data = response.raw.read(MAX_FIT_BYTES + 1, decode_content=True)
        if len(data) > MAX_FIT_BYTES:
            raise ValueError("Downloaded FIT exceeds 50 MiB.")
        title = title.strip() if isinstance(title, str) else ""
        if title and not title.casefold().startswith("zwift - "):
            title = f"Zwift - {title}"
        return activity_id, data, title
