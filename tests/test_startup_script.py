from pathlib import Path


def test_startup_script_uses_installed_tray_entrypoint_as_interpreter_anchor():
    script = Path("scripts/install_startup.ps1").read_text(encoding="utf-8")

    assert "wiim-lastfm-tray.exe" in script
    assert "Get-Command pythonw.exe" not in script
