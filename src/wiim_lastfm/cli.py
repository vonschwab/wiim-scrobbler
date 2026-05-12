from __future__ import annotations

import argparse
import sys
import time

from .config import ConfigError, get_devices, load_config
from .lastfm import LastFmClient
from .runner import default_state_path
from .scrobbler import DeviceScrobbler
from .state import ScrobbleState
from .upnp import PlayQueueClient
from .wiim import WiimClient

DEFAULT_HISTORY_SOURCES = (
    "tidal",
    "TIDAL",
    "spotify",
    "Spotify",
    "qobuz",
    "Qobuz",
    "amazon",
    "AmazonMusic",
    "deezer",
    "Deezer",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wiim-lastfm")
    parser.add_argument("--config", default="config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print WiiM playback data")
    inspect_parser.add_argument("host")

    history_parser = subparsers.add_parser(
        "history", help="Probe WiiM UPnP account history"
    )
    history_parser.add_argument("host")
    history_parser.add_argument("--number", type=int, default=10)
    history_parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Account source to try; can be repeated",
    )

    auth_parser = subparsers.add_parser("auth", help="Authorize with Last.fm")
    auth_parser.add_argument("--token", help="Use an existing Last.fm auth token")

    run_parser = subparsers.add_parser("run", help="Poll configured WiiM devices")
    run_parser.add_argument("--interval", type=float, default=20.0)
    run_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect":
            return inspect(args.host)
        if args.command == "history":
            return history(args.host, sources=args.sources, number=args.number)
        if args.command == "auth":
            return auth(args.config, token=args.token)
        if args.command == "run":
            return run(args.config, interval=args.interval, dry_run=args.dry_run)
    except (ConfigError, KeyError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


def inspect(host: str) -> int:
    wiim = WiimClient(host)
    status = wiim.player_status()
    track = wiim.current_track(duration_ms=status.duration_ms)
    print(f"host: {host}")
    print(f"playing: {status.is_playing}")
    print(f"position_ms: {status.position_ms}")
    print(f"duration_ms: {status.duration_ms}")
    print(f"mode: {status.mode}")
    print(f"artist: {track.artist}")
    print(f"title: {track.title}")
    print(f"album: {track.album or ''}")
    return 0


def history(host: str, sources: list[str] | None, number: int) -> int:
    client = PlayQueueClient(host)
    print("basic_user_info:")
    try:
        print(client.get_basic_user_info() or "<empty>")
    except Exception as exc:
        print(f"error: {exc}")

    for source in sources or list(DEFAULT_HISTORY_SOURCES):
        print(f"source: {source}")
        try:
            result = client.get_user_account_history(source, number)
        except Exception as exc:
            print(f"error: {exc}")
            continue
        print(result or "<empty>")
    return 0


def auth(config_path: str, token: str | None = None) -> int:
    config = load_config(config_path)
    lastfm = _lastfm_from_config(config, require_session=False)
    auth_token = token or lastfm.get_token()
    print("Open this URL and authorize the app:")
    print(lastfm.auth_url(auth_token))
    input("Press Enter after authorizing in your browser...")
    session_key = lastfm.get_session_key(auth_token)
    print("Add this to config.yaml under lastfm:")
    print(f"  session_key: {session_key}")
    return 0


def run(config_path: str, interval: float, dry_run: bool) -> int:
    config = load_config(config_path)
    lastfm = _lastfm_from_config(config, require_session=not dry_run)
    state = ScrobbleState(default_state_path())
    scrobblers = [
        DeviceScrobbler(
            device.name,
            WiimClient(device.host),
            lastfm,
            dry_run=dry_run,
            state=state,
        )
        for device in get_devices(config)
    ]

    while True:
        for scrobbler in scrobblers:
            try:
                message = scrobbler.poll_once()
            except Exception as exc:  # Keep other devices polling.
                message = f"{scrobbler.name}: {exc}"
            if message:
                print(message, flush=True)
        time.sleep(interval)


def _lastfm_from_config(
    config: dict[str, object], require_session: bool
) -> LastFmClient:
    lastfm_config = config.get("lastfm")
    if not isinstance(lastfm_config, dict):
        raise ConfigError("Config must include lastfm settings")

    api_key = str(lastfm_config.get("api_key") or "")
    shared_secret = str(lastfm_config.get("shared_secret") or "")
    session_key = lastfm_config.get("session_key")

    if not api_key:
        raise ConfigError("lastfm.api_key is required")
    if not shared_secret:
        raise ConfigError("lastfm.shared_secret is required")
    if require_session and not session_key:
        raise ConfigError("lastfm.session_key is required; run auth first")

    return LastFmClient(
        api_key=api_key,
        shared_secret=shared_secret,
        session_key=str(session_key) if session_key else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
