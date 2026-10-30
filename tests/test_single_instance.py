from wiim_lastfm.single_instance import ERROR_ALREADY_EXISTS, mutex_was_acquired
from wiim_lastfm.single_instance import SingleInstance, AlreadyRunningError
import pytest


def test_mutex_was_acquired_is_false_when_windows_reports_existing_mutex():
    assert mutex_was_acquired(ERROR_ALREADY_EXISTS) is False


def test_mutex_was_acquired_is_true_for_new_mutex():
    assert mutex_was_acquired(0) is True


def test_context_manager_releases_handle_when_instance_already_exists(monkeypatch):
    instance = SingleInstance("unused")
    released = []
    monkeypatch.setattr(instance, "acquire", lambda: False)
    monkeypatch.setattr(instance, "release", lambda: released.append(True))
    with pytest.raises(AlreadyRunningError):
        with instance: pass
    assert released == [True]
