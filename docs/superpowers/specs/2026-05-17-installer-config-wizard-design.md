# Installer Config Wizard Design

## Goal

Make the Windows installer usable without manual YAML editing by collecting Last.fm credentials and WiiM device details during setup.

## Installer Flow

The Inno Setup wizard adds configuration pages after the standard setup pages:

1. Last.fm configuration page
   - Collect `api_key`, `username`, `shared_secret`, and optional `session_key`.
   - Include instructions that `api_key` and `shared_secret` come from the user's Last.fm API account.
   - Explain that `session_key` is created by running the installed `Authorize Last.fm` shortcut after installation.

2. WiiM devices page
   - Start with one device row.
   - Default device name is `WiiM`.
   - Collect an IP address or host value for that device.
   - Provide a `+ Add another WiiM` button for additional devices.

3. Existing config handling
   - Write `%APPDATA%\WiiM Scrobbler\config.yaml`.
   - Do not overwrite an existing config unless the user explicitly checks `Replace existing config`.
   - If required fields are blank, keep the existing first-run template behavior.

## Output

The generated YAML uses the existing runtime shape:

```yaml
lastfm:
  api_key: "..."
  username: "..."
  shared_secret: "..."
  session_key: "..."

devices:
  - name: "WiiM"
    host: "https://192.168.1.50"
```

Device host entries are normalized by the installer. If the user enters `192.168.1.50`, the generated config writes `https://192.168.1.50`; if the user enters a full `http://` or `https://` URL, the installer preserves it.

## Testing

Packaging tests assert that the Inno Setup script contains the custom wizard, the Last.fm instructions, the add-device control, overwrite protection, and config YAML generation.
