from wiim_lastfm.cli import build_parser


def test_run_defaults_to_20_second_poll_interval():
    parser = build_parser()

    args = parser.parse_args(["run"])

    assert args.interval == 20.0
