from wiim_lastfm.runner import RunnerStatus
from wiim_lastfm.tray import build_parser, create_icon_image, runner_from_config_or_error


def test_tray_parser_defaults_to_config_and_20_second_interval():
    args = build_parser().parse_args([])

    assert args.config == "config.yaml"
    assert args.interval == 20.0
    assert args.dry_run is False


def test_create_icon_image_returns_square_rgba_image():
    image = create_icon_image(size=32)

    assert image.size == (32, 32)
    assert image.mode == "RGBA"


def test_runner_from_config_or_error_keeps_tray_available_on_config_error():
    def factory():
        raise ValueError("missing session")

    runner = runner_from_config_or_error(factory)

    assert runner.status == RunnerStatus.STOPPED
    assert runner.latest_message == "Startup error: missing session"
