import pytest

from idleon_reader.main import create_parser


def test_negative_playtime_is_rejected():
    parser = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--csv", "exports/latest", "--playtime-minutes", "-1"])


def test_repeatable_tags_preserve_order():
    parser = create_parser()
    args = parser.parse_args([
        "--csv", "exports/latest",
        "--tag", "session_start",
        "--tag", "level_10",
    ])
    assert args.tag == ["session_start", "level_10"]
