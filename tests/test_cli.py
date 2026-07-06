from app.cli import build_parser


def test_cli_parses_browser_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["browser-login"]).command == "browser-login"
    assert parser.parse_args(["browser-check-login"]).command == "browser-check-login"

    open_args = parser.parse_args(["browser-open-vacancy", "10"])
    assert open_args.command == "browser-open-vacancy"
    assert open_args.vacancy_id == 10

