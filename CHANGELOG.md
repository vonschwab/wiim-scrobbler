# Changelog

## 0.1.4 — 2026-10-30

- Identify NTS shows and archived episodes through NTS's catalogue when AirPlay
  hides the source artwork. Split combined artist/song metadata into separate
  Last.fm fields and omit show-level durations and placeholder albums.
- Cache confirmed NTS show titles on disk and share recognition between devices,
  the tray app, and the command-line runner.
- Timestamp NTS songs when first detected rather than using the show's elapsed
  position. Skip episode credits and missing song metadata.
- Block consecutive duplicate artist/song submissions across restarts and long
  gaps, ignoring album differences, case, and redundant whitespace.
- Check completed Last.fm history and server-corrected names before submitting.
  Defer when history cannot be checked. Keep uncertain submission attempts out
  of automatic retries, favouring duplicate avoidance over potentially missing
  a play whose submission cannot be confirmed.
- Save duplicate-protection state atomically, migrate existing history, and
  share the single-instance guard between the tray and command-line senders.

Existing incorrect or duplicate Last.fm entries are not changed. Other connected
applications can still submit their own duplicates. New NTS titles require an
indexed catalogue match and individual artist/song metadata.

## 0.1.3

- Existing Windows installer, configuration wizard, persisted pending queue,
  UPnP fallback, and NTS Infinite Mixtape support.
