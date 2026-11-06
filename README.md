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
python zwift_garmin.py latest --edge-1050
```

The command downloads the original FIT file for your latest completed cycling activity and writes `zwift-<activity-id>.garmin.fit` in the current directory. It accepts Zwift credentials from the terminal or environment variables and keeps them out of local files. The download uses undocumented Zwift Companion API endpoints. If they change, use the local conversion command below with a FIT file downloaded from the Zwift website. [Zwift FIT download instructions](https://support.zwift.com/en_us/locating-your-activity-log-and-workout-files-BykKO63fr) · [API reference implementation](https://github.com/benniblau/zwift-mcp)

## Convert a local FIT file

```powershell
python zwift_garmin.py convert ride.fit -o ride.garmin.fit
```

Without `-o`, the converter creates a `.garmin.fit` copy next to the source. It refuses to overwrite existing files. Both `latest` and `convert` support these options:

- `--edge-1050` sets the Garmin Edge 1050 product code and leaves the Unit ID empty.
- `--fenix-8` sets the standard Garmin fēnix 8 product code and leaves the Unit ID empty.
- `--garmin-reference device-ride.fit` uses the product code and Unit ID from an original activity recorded by your Garmin device. Use this option by itself for the device identity.
- `--indoor` changes the FIT sport subtype to indoor cycling.

## Upload to Garmin Connect

Use the [Garmin Connect import page](https://connect.garmin.com/modern/import-data) or install the optional upload dependency:

```powershell
python -m pip install garminconnect==0.3.20
python zwift_garmin.py upload ride.garmin.fit
```

Add `--upload` to `latest` or `convert` to upload after conversion. If the same output already exists in the current directory, `latest` skips the upload. Use the standalone `upload` command to upload an existing file or retry a failed upload.

### Run without prompts

Set these variables in the environment that starts the command. If your task runner supports secrets, use its secret settings for passwords.

| Operation | Environment variables |
| --- | --- |
| Zwift download | `ZWIFT_USER` (email) and `ZWIFT_PASSWORD` |
| Garmin upload | `GARMIN_EMAIL` and `GARMIN_PASSWORD`, or `GARMINTOKENS` pointing to a saved Garmin session directory |

```powershell
python zwift_garmin.py latest --edge-1050 --non-interactive
python zwift_garmin.py latest --fenix-8 --upload --non-interactive
```

In non-interactive mode, missing credentials or a Garmin MFA prompt cause the command to exit with an error. For a Garmin account with MFA, create a session with the library's login example and point `GARMINTOKENS` at its session directory. [Garmin login example](https://github.com/cyberjunky/python-garminconnect/blob/master/example.py)

## Verify challenge credit

Garmin requires joining the challenge and meeting its listed requirements within the challenge period. Its support guidance includes activities recorded in Tacx Training and excludes third-party sources such as Zwift from badge eligibility. TrainingPeaks Virtual has its own Garmin authorization flow. The exact server-side rules for challenge credit are undocumented. [Garmin badges](https://support.garmin.com/en-US/?faq=6pECo6UIFn7ergw8kNmfu9) · [Garmin eligibility guidance](https://support.garmin.ru/support/solutions/articles/26000043125) · [TrainingPeaks Virtual integration](https://help.trainingpeaks.com/hc/en-us/articles/41893283744909-TrainingPeaks-Virtual-Connections-Screenshots)

1. Check the activity requirements for an active challenge you have joined and record your current progress.
2. Import a converted ride that is absent from Garmin Connect. An already synced ride may be rejected as a duplicate.
3. Check the imported activity's device and sport, then check whether the challenge distance or time increased.
4. If the challenge requires indoor cycling, try `--indoor` on a separate eligible ride. You can also test a reference FIT from your own Garmin device. Change one setting per trial.

Related tools include Fit File Faker, which rewrites device metadata and can upload to Garmin, and fitff, which uses an external device-changing service. This project rewrites FIT files locally. The Tacx Windows profile comes from a community report. [Fit File Faker](https://github.com/jat255/Fit-File-Faker) · [fitff](https://github.com/pitoniak32/fitff) · [Tacx Windows report](https://www.reddit.com/r/Zwift/comments/1jv641i/)
