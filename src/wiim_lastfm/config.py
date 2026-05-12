from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import DeviceConfig


class ConfigError(ValueError):
    pass


CONFIG_TEMPLATE = """lastfm:
  api_key: "put-your-lastfm-api-key-here"
  username: "put-your-lastfm-username-here"
  shared_secret: "put-your-lastfm-shared-secret-here"
  session_key: "run-auth-to-get-this"

devices:
  - name: "Living Room WiiM"
    host: "https://192.168.1.50"
"""


def default_user_config_path() -> Path:
    import os

    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / "WiiM Scrobbler" / "config.yaml"


def ensure_user_config(path: str | Path | None = None) -> bool:
    config_path = Path(path) if path is not None else default_user_config_path()
    if config_path.exists():
        return False
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    return True


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config file must contain a YAML mapping")
    return data


def get_devices(config: dict[str, Any]) -> list[DeviceConfig]:
    devices = config.get("devices")
    if not isinstance(devices, list) or not devices:
        raise ConfigError("Config must include at least one device")

    parsed: list[DeviceConfig] = []
    for index, item in enumerate(devices, start=1):
        if not isinstance(item, dict) or not item.get("host"):
            raise ConfigError(f"Device #{index} must include host")
        parsed.append(
            DeviceConfig(name=str(item.get("name") or item["host"]), host=str(item["host"]))
        )
    return parsed
