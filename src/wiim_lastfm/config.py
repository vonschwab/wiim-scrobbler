from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import DeviceConfig


class ConfigError(ValueError):
    pass


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
