from pathlib import Path

import pytest

from wiim_lastfm.config import (
    CONFIG_TEMPLATE,
    ConfigError,
    default_user_config_path,
    ensure_user_config,
    get_settlement_seconds,
)


def test_default_user_config_path_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", "C:\\Users\\Dylan\\AppData\\Roaming")

    assert default_user_config_path() == Path(
        "C:\\Users\\Dylan\\AppData\\Roaming\\WiiM Scrobbler\\config.yaml"
    )


def test_ensure_user_config_creates_template_when_missing(tmp_path):
    path = tmp_path / "config.yaml"

    created = ensure_user_config(path)

    assert created is True
    assert "api_key: \"put-your-lastfm-api-key-here\"" in path.read_text(encoding="utf-8")


def test_ensure_user_config_does_not_overwrite_existing_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("existing: true\n", encoding="utf-8")

    created = ensure_user_config(path)

    assert created is False
    assert path.read_text(encoding="utf-8") == "existing: true\n"


def test_public_config_template_does_not_include_personal_credentials():
    assert "4063180b7849e7bf7bdf84d8c665a3f3" not in CONFIG_TEMPLATE
    assert "vonschwab" not in CONFIG_TEMPLATE


def test_settlement_seconds_defaults_to_90():
    assert get_settlement_seconds({}) == 90


def test_settlement_seconds_can_be_configured():
    assert get_settlement_seconds({"scrobble": {"settlement_seconds": 120}}) == 120


def test_settlement_seconds_rejects_negative_value():
    with pytest.raises(ConfigError, match="zero or greater"):
        get_settlement_seconds({"scrobble": {"settlement_seconds": -1}})
