"""DietCode fork: CLI command name surfaces through argparse and parser help."""

from hermes_cli._parser import build_top_level_parser
from hermes_constants import get_cli_command, get_product_display_name


def test_top_level_parser_prog_is_dietcode():
    parser, _sub, _chat = build_top_level_parser()
    assert parser.prog == get_cli_command() == "dietcode"
    assert get_product_display_name() in parser.description
    assert "dietcode update" in parser.epilog
    assert "hermes-agent-dev" in parser.epilog
