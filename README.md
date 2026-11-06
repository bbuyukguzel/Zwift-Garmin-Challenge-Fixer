# Zwift Garmin Challenge Fixer

Convert a Zwift ride to a FIT file for Garmin Connect. By default, the converter writes Garmin Tacx Training Windows as the recording device. The ride stays virtual, and GPS, power, heart rate, cadence, timestamps, laps, and developer fields are preserved.

## Setup

Use Python 3.12 or later. Run these commands from the project directory.

```powershell
python -m pip install -r requirements.txt
```

## Download your latest Zwift ride

After saving the ride to your Zwift account, run this on any computer with Python.

```powershell
python zwift_garmin.py latest --device "Edge 840"
```

The command downloads the original FIT file for your latest completed cycling activity and writes `zwift-<activity-id>.garmin.fit` in the current directory. It accepts Zwift credentials from the terminal or environment variables and keeps them out of local files. The download uses undocumented Zwift Companion API endpoints. If they change, use the local conversion command below with a FIT file downloaded from the Zwift website. [Zwift FIT download instructions](https://support.zwift.com/en_us/locating-your-activity-log-and-workout-files-BykKO63fr) · [API reference implementation](https://github.com/benniblau/zwift-mcp)

## Convert a local FIT file

```powershell
python zwift_garmin.py convert ride.fit -o ride.garmin.fit
```

Without `-o`, `convert` creates a `.garmin.fit` copy next to the source. This command refuses to overwrite existing files. Both `latest` and `convert` support these options:

- `--device MODEL_OR_CODE` sets the Garmin device product and leaves the Unit ID empty. Use an exact FIT profile name such as `fenix6` or `edge_840`, a readable spelling such as `"Fēnix 6"` or `"Edge 840"`, or a numeric product code such as `4062`. Names come from the installed Garmin FIT SDK. The `--edge-1050` and `--fenix-8` aliases also work. [Garmin FIT product profile](https://github.com/garmin/fit-python-sdk/blob/main/garmin_fit_sdk/profile.py)
- `--garmin-reference device-ride.fit` uses the product code and Unit ID from an original activity recorded by your Garmin device. Use this option by itself for the device identity.
- `--indoor` changes the FIT sport subtype to indoor cycling.

## Upload to Garmin Connect

Use the [Garmin Connect import page](https://connect.garmin.com/modern/import-data) or install the optional upload dependency:

```powershell
python -m pip install garminconnect==0.3.20
python zwift_garmin.py upload ride.garmin.fit
```

Add `--upload` to `latest` or `convert` to upload after conversion. If the output for the same Zwift activity differs, `latest` replaces the local FIT. If the output is identical, it reuses the existing file. In both cases, `--upload` sends the file to Garmin. Use the standalone `upload` command to send a local file without downloading from Zwift.

Garmin can acknowledge a file with an upload ID and leave both result lists empty. In that case, the command reports acceptance. Check Garmin Connect for the activity before retrying.

### Run without prompts

Set these variables in the environment that starts the command. If your task runner supports secrets, use its secret settings for passwords.

| Operation | Environment variables |
| --- | --- |
| Zwift download | `ZWIFT_USER` (email) and `ZWIFT_PASSWORD` |
| Garmin upload | `GARMIN_EMAIL` and `GARMIN_PASSWORD`, or `GARMINTOKENS` pointing to a saved Garmin session directory |

```powershell
python zwift_garmin.py latest --device "Fenix 6" --non-interactive
python zwift_garmin.py latest --device "Fenix 8" --upload --non-interactive
```

In non-interactive mode, missing credentials or a Garmin MFA challenge cause the command to exit with an error. To set up a saved session, set `GARMIN_EMAIL` and `GARMIN_PASSWORD` in your environment and run:

```powershell
$env:GARMINTOKENS = Join-Path $env:LOCALAPPDATA 'ZwiftGarmin\GarminSession'
python zwift_garmin.py garmin-login
```

Enter the MFA code if Garmin requests it. On future runs, set `GARMINTOKENS` to the same directory. The saved session can authorize uploads without the Garmin email or password. If a previous upload stopped at MFA, retry the already converted file with `python zwift_garmin.py upload <file.fit> --non-interactive`.

## Verify challenge credit

For November Ride to 200, a Zwift ride counted after conversion with an original fēnix 8 FIT as the reference. The reference supplies the watch's model and real Unit ID. The model-only fēnix 8 and Tacx Training iOS trials did not count on the same account.

```powershell
python zwift_garmin.py latest --garmin-reference .\fenix8-reference.fit --upload --non-interactive
```

Export an original activity from your own Garmin device to create the reference file. Keep it local because it contains activity data and your device's Unit ID.

Garmin requires joining the challenge and meeting its listed requirements within the challenge period. Its support guidance includes activities recorded in Tacx Training and excludes third-party sources such as Zwift from badge eligibility. TrainingPeaks Virtual has its own Garmin authorization flow. The exact server-side rules for challenge credit are undocumented. [Garmin badges](https://support.garmin.com/en-US/?faq=6pECo6UIFn7ergw8kNmfu9) · [Garmin eligibility guidance](https://support.garmin.ru/support/solutions/articles/26000043125) · [TrainingPeaks Virtual integration](https://help.trainingpeaks.com/hc/en-us/articles/41893283744909-TrainingPeaks-Virtual-Connections-Screenshots)

1. Check the activity requirements for an active challenge you have joined and record your current progress.
2. Import a converted ride that is absent from Garmin Connect. An already synced ride may be rejected as a duplicate.
3. Check the imported activity's device and sport, then check whether the challenge distance or time increased.
4. If the challenge requires indoor cycling, try `--indoor` on a separate eligible ride. You can also test a reference FIT from your own Garmin device. Change one setting per trial.

Related tools include Fit File Faker, which rewrites device metadata and can upload to Garmin, and fitff, which uses an external device-changing service. This project rewrites FIT files locally. The Tacx Windows profile comes from a community report. [Fit File Faker](https://github.com/jat255/Fit-File-Faker) · [fitff](https://github.com/pitoniak32/fitff) · [Tacx Windows report](https://www.reddit.com/r/Zwift/comments/1jv641i/)
