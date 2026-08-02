# WiiM Last.fm Scrobbler

A lightweight Windows-friendly Last.fm scrobbler for WiiM devices, using the
local WiiM API to detect playback and submit tracks to Last.fm.

## Setup

### Windows installer

Download and run the latest `wiim-scrobbler-setup-*.exe` from the GitHub
release. The installer adds `WiiM Scrobbler` to the Start Menu and can
optionally create a startup shortcut so the tray app starts when you sign in.

The installer can write your user config during setup. It asks for:

- Last.fm API key, username, and shared secret.
- Optional Last.fm session key.
- One WiiM device name and IP address, with a `+ Add another WiiM` button for
  additional devices.

Get the Last.fm API key and shared secret from your Last.fm API account page:

```text
https://www.last.fm/api/account
```

The session key is created by authorizing the app. If you do not already have
one, leave it blank during setup and run this Start Menu shortcut after install:

```text
WiiM Scrobbler > Authorize Last.fm
```

Open the printed URL, approve access, then press Enter in the terminal. Add the
printed `session_key` to your config and restart the tray app.

The installer writes config here:

```text
%APPDATA%\WiiM Scrobbler\config.yaml
```

It will not overwrite an existing config unless you choose `Replace existing
config`. You can also use the tray menu's `Open config` action to edit the file
later.

When upgrading an existing installation, the installer detects that config file
and skips the credential and device pages automatically. To intentionally reopen
the setup wizard and replace the config, run the installer with
`/RECONFIGURE=1`.

### Development setup

```powershell
python -m pip install -e ".[dev]"
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml`:

- Add each WiiM device IP under `devices`.
- Add your Last.fm API shared secret under `lastfm.shared_secret`.
- Leave `session_key` blank until authorization.

The packaged tray app creates its user config here on first run:

```text
%APPDATA%\WiiM Scrobbler\config.yaml
```

Use the tray menu's `Open config` action to edit it.

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

If a WiiM is reachable but does not expose the local HTTP API, the client falls
back to UPnP AVTransport on port 49152 for playback state, position, duration,
and track metadata.

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

The scrobbler waits until a track has been observed in at least two polling
cycles. When the next track starts, or playback stops, the completed play enters
a local pending queue. After a 90-second settlement window, the app checks your
Last.fm recent history and submits only if another connected service has not
already scrobbled the track. Set `scrobble.settlement_seconds` in the config to
tune that delay.

The pending queue and duplicate protection history are stored locally, so
restarting the app does not lose completed plays or resubmit recent tracks.
Matching multi-room observations collapse into one queued play.

## NTS Radio Infinite Mixtapes

An NTS Infinite Mixtape is one continuous stream, so a WiiM reports the mixtape
name (`ISLAND TIME`, `POOLSIDE`) as the track title and never changes it. The
track NTS is actually playing is published separately, as ICY `StreamTitle`
metadata on the mixtape stream, formatted as `ARTIST • TITLE` or
`Artist - Title`.

How that string reaches the WiiM depends on how you play it:

- AirPlay from the NTS app forwards it into the WiiM's `artist` field, so the
  device reports the mixtape name as the title and the whole `ARTIST • TITLE`
  string as the artist.
- Chromecast drops it entirely, leaving the WiiM with no track metadata at all.

The scrobbler recognises mixtape playback by matching the reported title against
the NTS mixtape catalogue, then takes the track from the device's `artist` field
when it is there and reads the mixtape's stream metadata when it is not. Either
way Last.fm receives the real artist and title rather than the mixtape name.

When NTS publishes no track — between tracks, or when it sends an episode credit
(`JACK SAPSED, ISLAND TIME VOL 17`) or a broadcast date (`26 Jul 2026`) instead
— nothing is scrobbled for that play. NTS's track feed does go quiet for long
stretches, and no scrobbles happen while it is.

WiiM firmware writes `unknow` into metadata fields it has no value for. That is
treated as missing metadata, not as an artist named `unknow`.

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
