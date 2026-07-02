import pytest

from asciilint.policy import (
    CharacterPolicy,
    CodePointRange,
    PolicyError,
    parse_code_point,
)


def test_parse_code_point_forms() -> None:
    assert parse_code_point("U+00E9") == 0x00E9
    assert parse_code_point("0x7f") == 0x7F
    assert parse_code_point("127") == 127
    assert parse_code_point("é") == ord("é")


def test_parse_range_forms() -> None:
    assert CodePointRange.parse("U+0000-U+007F") == CodePointRange(0, 127)
    assert CodePointRange.parse("0x20..0x7e") == CodePointRange(32, 126)
    assert CodePointRange.parse("a-z") == CodePointRange(ord("a"), ord("z"))


def test_policy_denies_outside_allowlist_and_denylist_wins() -> None:
    policy = CharacterPolicy.from_config(
        allowed_chars=("é",),
        allowed_ranges=("U+0000-U+007F",),
        disallowed_chars=("x",),
        disallowed_ranges=(),
    )

    assert policy.is_allowed("a")
    assert policy.is_allowed("é")
    assert not policy.is_allowed("π")
    assert not policy.is_allowed("x")
    assert policy.violation_reason("x") == "denied by policy"


def test_invalid_policy_range() -> None:
    with pytest.raises(PolicyError):
        CodePointRange.parse("U+0100-U+0000")
