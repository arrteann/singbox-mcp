from singbox_mcp.__main__ import build_parser


def test_cli_requires_command():
    parser = build_parser()
    try:
        parser.parse_args([])
        raised = False
    except SystemExit:
        raised = True
    assert raised


def test_cli_parses_known_commands():
    parser = build_parser()
    for command in ("scrape", "build-index", "serve"):
        args = parser.parse_args(["--log-level", "DEBUG", command])
        assert args.command == command
        assert args.log_level == "DEBUG"
