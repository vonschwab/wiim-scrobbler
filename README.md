# WiiM Last.fm Scrobbler

A lightweight Windows-friendly Last.fm scrobbler for WiiM devices, using the
local WiiM API to detect playback and submit tracks to Last.fm.

## Setup

```powershell
python -m pip install -e ".[dev]"
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml`:

- Add each WiiM device IP under `devices`.
- Add your Last.fm API shared secret under `lastfm.shared_secret`.
- Leave `session_key` blank until authorization.

## Authorize Last.fm

```powershell
python -m wiim_lastfm.cli --config config.yaml auth
```

Open the printed URL, approve access, then press Enter in the terminal. Add the printed
`session_key` to `config.yaml`.

## Inspect a WiiM

```powershell
python -m wiim_lastfm.cli inspect 192.168.1.50
```

This calls:

- `getPlayerStatus` for play state, position, duration, and source mode
- `getMetaInfo` for artist, title, and album

## Probe WiiM History

```powershell
python -m wiim_lastfm.cli history https://192.168.1.97 --number 10
```

This calls the proprietary UPnP `PlayQueue` service. On tested firmware,
`GetBasicUserInfo` returns service account information, but
`GetUserAccountHistory` may return a WiiM `GetUserInfo failed` fault even for
logged-in services. Treat this as a diagnostic probe until a usable history
response is confirmed.

## Run

```powershell
python -m wiim_lastfm.cli --config config.yaml run
```

By default, configured devices are checked every 20 seconds. Override that with
`--interval` if you want faster or slower polling.

Use `--dry-run` to see detections without sending anything to Last.fm:

```powershell
python -m wiim_lastfm.cli --config config.yaml run --dry-run
```

The scrobbler submits after at least half the track has played, or after four minutes
for longer tracks.

## Tray App

Run the Windows tray app:

```powershell
wiim-lastfm-tray --config config.yaml
```

The tray app starts the same scrobbler in the background, writes logs to:

```text
%LOCALAPPDATA%\WiimScrobbler\wiim-scrobbler.log
```

and keeps restart-safe duplicate protection state at:

```text
%LOCALAPPDATA%\WiimScrobbler\state.json
```

The log rotates at about 1 MB with five backups. The tray app also enforces a
single running instance so a second startup or manual launch does not create
duplicate scrobblers.

The tray menu exposes actions to open the config, open the log, or quit.

Install it to start when you sign in to Windows:

```powershell
.\scripts\install_startup.ps1
```

Remove the startup shortcut:

```powershell
.\scripts\uninstall_startup.ps1
```
