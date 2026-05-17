from pathlib import Path


def test_pyinstaller_spec_builds_tray_and_cli_entrypoints():
    spec = Path("packaging/wiim-scrobbler.spec").read_text(encoding="utf-8")

    assert "source_root" in spec
    assert 'spec_dir / "tray_entry.py"' in spec
    assert 'spec_dir / "cli_entry.py"' in spec
    assert "name='WiiM Scrobbler'" in spec
    assert "name='WiiM Scrobbler CLI'" in spec
    assert "console=False" in spec
    assert "console=True" in spec


def test_inno_setup_script_installs_executables_and_startup_task():
    script = Path("packaging/wiim-scrobbler.iss").read_text(encoding="utf-8")

    assert "#define MyAppName \"WiiM Scrobbler\"" in script
    assert "WiiM Scrobbler.exe" in script
    assert "WiiM Scrobbler CLI.exe" in script
    assert "Authorize Last.fm" in script
    assert "{userstartup}\\WiiM Scrobbler.lnk" in script


def test_inno_setup_script_collects_config_values_in_wizard():
    script = Path("packaging/wiim-scrobbler.iss").read_text(encoding="utf-8")

    assert "CreateInputQueryPage" in script
    assert "Last.fm API account" in script
    assert "API key" in script
    assert "shared secret" in script
    assert "session key" in script
    assert "Authorize Last.fm" in script
    assert "Replace existing config" in script
    assert "+ Add another WiiM" in script
    assert "Device name" in script
    assert "WiiM" in script
    assert "SaveConfigFile" in script
    assert "%APPDATA%\\WiiM Scrobbler\\config.yaml" in script


def test_windows_build_script_runs_pyinstaller_then_inno():
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    assert "python -m PyInstaller" in script
    assert "PyInstaller failed" in script
    assert "ISCC.exe" in script
    assert "Inno Setup failed" in script
    assert "packaging\\wiim-scrobbler.iss" in script
