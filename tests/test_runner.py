from wiim_lastfm.runner import BackgroundScrobblerRunner, RunnerStatus


class Poller:
    def __init__(self, messages):
        self.messages = list(messages)
        self.calls = 0

    def poll_once(self):
        self.calls += 1
        if self.messages:
            return self.messages.pop(0)
        return None


class FailingPoller:
    name = "bad device"

    def poll_once(self):
        raise RuntimeError("network down")


def test_runner_poll_cycle_records_latest_message():
    runner = BackgroundScrobblerRunner([Poller(["scrobbled Track"])], interval=20)

    runner.poll_cycle()

    assert runner.status == RunnerStatus.RUNNING
    assert runner.latest_message == "scrobbled Track"
    assert runner.error_count == 0


def test_runner_poll_cycle_records_errors_and_keeps_running():
    runner = BackgroundScrobblerRunner([FailingPoller()], interval=20)

    runner.poll_cycle()

    assert runner.status == RunnerStatus.RUNNING
    assert runner.latest_message == "bad device: network down"
    assert runner.error_count == 1


def test_runner_start_and_stop_manage_background_thread():
    runner = BackgroundScrobblerRunner([Poller([])], interval=0.01)

    runner.start()
    runner.stop(timeout=1)

    assert runner.status == RunnerStatus.STOPPED
