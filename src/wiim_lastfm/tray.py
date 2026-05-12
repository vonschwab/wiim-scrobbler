from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

from PIL import Image, ImageDraw
import pystray

from .runner import BackgroundScrobblerRunner
from .single_instance import SingleInstance


APP_NAME = "WiiM Last.fm Scrobbler"
MUTEX_NAME = "Local\\WiimScrobblerTray"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_path = default_log_path()
    configure_logging(log_path)
    logging.info("Starting %s", APP_NAME)

    instance = SingleInstance(MUTEX_NAME)
    try:
        acquired = instance.acquire()
    except Exception:
        logging.exception("Could not acquire single-instance guard")
        return 2
    if not acquired:
        logging.warning("Tray app is already running")
        instance.release()
        return 2

    runner = runner_from_config_or_error(
        lambda: BackgroundScrobblerRunner.from_config(
            args.config,
            interval=args.interval,
            dry_run=args.dry_run,
        )
    )

    icon = pystray.Icon(
        "wiim-lastfm",
        create_icon_image(),
        APP_NAME,
        menu=build_menu(runner, Path(args.config), log_path),
    )
    try:
        icon.run()
        return 0
    finally:
        runner.stop(timeout=5)
        instance.release()
        logging.info("Stopped %s", APP_NAME)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wiim-lastfm-tray")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--interval", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def runner_from_config_or_error(factory) -> BackgroundScrobblerRunner:
    try:
        runner = factory()
    except Exception as exc:
        logging.exception("Could not start scrobbler: %s", exc)
        runner = BackgroundScrobblerRunner([], interval=20.0)
        runner.latest_message = f"Startup error: {exc}"
        return runner

    runner.start()
    return runner


def build_menu(
    runner: BackgroundScrobblerRunner, config_path: Path, log_path: Path
) -> pystray.Menu:
    def quit_app(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        runner.stop(timeout=5)
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem(lambda _item: f"Status: {runner.status.value}", None, enabled=False),
        pystray.MenuItem(
            lambda _item: f"Last: {runner.latest_message}",
            None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open config", lambda _icon, _item: open_path(config_path)),
        pystray.MenuItem("Open log", lambda _icon, _item: open_path(log_path)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )


def create_icon_image(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (22, 26, 32, 255))
    draw = ImageDraw.Draw(image)
    margin = max(2, size // 8)
    inner = max(4, size // 3)
    width = max(2, size // 12)
    draw.ellipse((margin, margin, size - margin, size - margin), fill=(68, 166, 255, 255))
    draw.ellipse((inner, inner, size - inner, size - inner), fill=(22, 26, 32, 255))
    draw.arc(
        (margin * 2, margin * 2, size - margin * 2, size - margin * 2),
        305,
        55,
        fill=(245, 247, 250, 255),
        width=width,
    )
    draw.arc(
        (margin // 2, margin // 2, size - margin // 2, size - margin // 2),
        305,
        55,
        fill=(245, 247, 250, 255),
        width=width,
    )
    return image


def default_log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "WiimScrobbler" / "wiim-scrobbler.log"


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def open_path(path: Path) -> None:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except OSError as exc:
        logging.exception("Could not open %s: %s", path, exc)


if __name__ == "__main__":
    raise SystemExit(main())
