from __future__ import annotations

import enum
import logging
import threading
import time
from collections.abc import Iterable
from typing import Protocol

from .config import get_devices, load_config
from .lastfm import LastFmClient
from .scrobbler import DeviceScrobbler
from .wiim import WiimClient


class Poller(Protocol):
    name: str

    def poll_once(self) -> str | None: ...


class RunnerStatus(enum.Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"


class BackgroundScrobblerRunner:
    def __init__(self, pollers: Iterable[Poller], interval: float = 20.0) -> None:
        self.pollers = list(pollers)
        self.interval = interval
        self.status = RunnerStatus.STOPPED
        self.latest_message = "Stopped"
        self.error_count = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_config(
        cls, config_path: str, interval: float = 20.0, dry_run: bool = False
    ) -> BackgroundScrobblerRunner:
        config = load_config(config_path)
        lastfm = _lastfm_from_config(config, require_session=not dry_run)
        return cls(
            [
                DeviceScrobbler(
                    device.name,
                    WiimClient(device.host),
                    lastfm,
                    dry_run=dry_run,
                )
                for device in get_devices(config)
            ],
            interval=interval,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.status = RunnerStatus.RUNNING
        self.latest_message = "Running"
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        self.status = RunnerStatus.STOPPING
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        self.status = RunnerStatus.STOPPED
        self.latest_message = "Stopped"

    def run_forever(self) -> None:
        self.status = RunnerStatus.RUNNING
        while not self._stop_event.is_set():
            self.poll_cycle()
            self._stop_event.wait(self.interval)
        self.status = RunnerStatus.STOPPED

    def poll_cycle(self) -> None:
        self.status = RunnerStatus.RUNNING
        for poller in self.pollers:
            try:
                message = poller.poll_once()
            except Exception as exc:
                name = getattr(poller, "name", "device")
                message = f"{name}: {exc}"
                logging.warning(message)
                with self._lock:
                    self.error_count += 1
            if message:
                with self._lock:
                    self.latest_message = message
                logging.info(message)
                print(message, flush=True)


def _lastfm_from_config(config: dict[str, object], require_session: bool) -> LastFmClient:
    lastfm_config = config.get("lastfm")
    if not isinstance(lastfm_config, dict):
        raise ValueError("Config must include lastfm settings")

    api_key = str(lastfm_config.get("api_key") or "")
    shared_secret = str(lastfm_config.get("shared_secret") or "")
    session_key = lastfm_config.get("session_key")

    if not api_key:
        raise ValueError("lastfm.api_key is required")
    if not shared_secret:
        raise ValueError("lastfm.shared_secret is required")
    if require_session and not session_key:
        raise ValueError("lastfm.session_key is required; run auth first")

    return LastFmClient(
        api_key=api_key,
        shared_secret=shared_secret,
        session_key=str(session_key) if session_key else None,
    )
