from wiim_lastfm.single_instance import ERROR_ALREADY_EXISTS, mutex_was_acquired


def test_mutex_was_acquired_is_false_when_windows_reports_existing_mutex():
    assert mutex_was_acquired(ERROR_ALREADY_EXISTS) is False


def test_mutex_was_acquired_is_true_for_new_mutex():
    assert mutex_was_acquired(0) is True
