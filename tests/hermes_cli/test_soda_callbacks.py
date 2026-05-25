"""DietCode soda callback helpers."""

from unittest.mock import patch

from hermes_cli import soda_callbacks as soda


def test_fizz_spinner_frames_default():
    frames = soda.resolve_fizz_spinner_frames()
    assert "○" in frames
    assert len(frames) >= 8


def test_soda_tool_verb_patch():
    emoji, verb = soda.soda_tool_verb("patch")
    assert emoji == "🫧"
    assert "patch" in verb or verb == "fizz-patch"


def test_is_dietcode_skin_by_name():
    assert soda.is_dietcode_skin("dietcode") is True
    assert soda.is_dietcode_skin("default") is False


def test_resolve_spinner_type_from_skin():
    from hermes_cli.skin_engine import SkinConfig

    skin = SkinConfig(name="dietcode", spinner={"type": "fizz"})
    with patch("hermes_cli.skin_engine.get_active_skin", return_value=skin):
        assert soda.resolve_spinner_type("dots") == "fizz"
