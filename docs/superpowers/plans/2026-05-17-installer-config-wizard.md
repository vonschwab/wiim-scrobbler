# Installer Config Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native Inno Setup wizard pages that write the WiiM Scrobbler user config during installation.

**Architecture:** Keep the installer wizard inside `packaging/wiim-scrobbler.iss` using Inno Setup Pascal Script. Preserve the existing Python runtime config format so the tray and CLI need no changes.

**Tech Stack:** Inno Setup 6 Pascal Script, PyInstaller, pytest packaging assertions.

---

### Task 1: Add Packaging Tests

**Files:**
- Modify: `tests/test_packaging.py`

- [ ] Add assertions that the Inno script includes `CreateInputQueryPage`, Last.fm help text, `Replace existing config`, `Add another WiiM`, and `SaveConfigFile`.

- [ ] Run `pytest tests/test_packaging.py -q -p no:cacheprovider` and verify the new assertions fail before implementation.

### Task 2: Implement Installer Wizard

**Files:**
- Modify: `packaging/wiim-scrobbler.iss`

- [ ] Add `[Code]` declarations for Last.fm inputs, WiiM device rows, overwrite checkbox, and config writing.

- [ ] Add `InitializeWizard` to create:
  - Last.fm settings page with API key, username, shared secret, and session key fields.
  - Instruction labels explaining the Last.fm API account and `Authorize Last.fm` session-key workflow.
  - WiiM page with default device name `WiiM`, host/IP input, and `+ Add another WiiM`.
  - Existing config page with `Replace existing config`.

- [ ] Add `CurStepChanged` handling to write `%APPDATA%\WiiM Scrobbler\config.yaml` at install time when no existing config blocks the write.

### Task 3: Verify and Rebuild

**Files:**
- Modify: none unless verification exposes issues.

- [ ] Run `pytest -q -p no:cacheprovider` and verify all tests pass.

- [ ] Run `powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1` and verify the installer compiles.

- [ ] Run `git diff --check`.

- [ ] Commit and push the finished wizard changes.
