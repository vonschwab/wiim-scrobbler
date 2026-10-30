from wiim_lastfm.cli import build_parser

import pytest

from wiim_lastfm import cli
from wiim_lastfm.models import Track


def test_run_defaults_to_20_second_poll_interval():
    parser = build_parser()

    args = parser.parse_args(["run"])

    assert args.interval == 20.0


def test_cli_run_uses_shared_persistent_nts_recognition(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        "lastfm:\n  api_key: key\n  shared_secret: secret\n"
        "devices:\n  - host: 192.168.1.1\n  - host: 192.168.1.2\n",
        encoding="utf-8",
    )
    (tmp_path / "nts-shows.json").write_text('["astral garden w/ nailah hunter"]')
    pollers = []
    class Poller:
        def __init__(self, *args, **kwargs):
            self.nts = kwargs["nts"]
            pollers.append(self)
        def poll_once(self): return None
    def stop(_interval): raise KeyboardInterrupt
    monkeypatch.setattr(cli, "default_state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(cli, "DeviceScrobbler", Poller)
    monkeypatch.setattr(cli.time, "sleep", stop)

    with pytest.raises(KeyboardInterrupt):
        cli.run(str(config), interval=20, dry_run=True)

    assert pollers[0].nts is pollers[1].nts
    resolver = pollers[0].nts
    resolver._fetch_catalog = lambda: []
    assert resolver.resolve(Track("L’Rain - Elmyra", "ASTRAL GARDEN W/ NAILAH HUNTER", None, None)) == Track("L’Rain", "Elmyra", None, None)


def test_cli_cannot_start_sender_while_tray_is_running(monkeypatch):
    from wiim_lastfm.single_instance import AlreadyRunningError, MUTEX_NAME
    class Occupied:
        def __init__(self, name): assert name == MUTEX_NAME
        def __enter__(self): raise AlreadyRunningError("already running")
        def __exit__(self, *args): pass
    monkeypatch.setattr(cli, "SingleInstance", Occupied)
    monkeypatch.setattr(cli, "_run", lambda *a: pytest.fail("second sender started"))
    with pytest.raises(AlreadyRunningError): cli.run("unused", 20, False)
