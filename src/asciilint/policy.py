"""Character policy parsing and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

MAX_CODE_POINT = 0x10FFFF


class PolicyError(ValueError):
    """Raised when a character policy cannot be parsed."""


@dataclass(frozen=True, slots=True)
class CodePointRange:
    """Inclusive Unicode code point range."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end > MAX_CODE_POINT or self.start > self.end:
            msg = f"invalid code point range: U+{self.start:04X}-U+{self.end:04X}"
            raise PolicyError(msg)

    def contains(self, char: str) -> bool:
        """Return whether ``char`` is inside this range."""

        return self.start <= ord(char) <= self.end

    @classmethod
    def parse(cls, value: str) -> CodePointRange:
        """Parse a range string.

        Supported forms include ``U+0000-U+007F``, ``0x20..0x7e``,
        ``32-126``, a single code point such as ``U+00A9``, or a single
        literal character.
        """

        text = value.strip()
        if not text:
            msg = "empty code point range"
            raise PolicyError(msg)

        parts = _split_range(text)
        if parts is None:
            code_point = parse_code_point(text)
            return cls(code_point, code_point)

        start = parse_code_point(parts[0])
        end = parse_code_point(parts[1])
        return cls(start, end)


def parse_code_point(value: str) -> int:
    """Parse one Unicode code point from a string."""

    text = value.strip()
    if not text:
        msg = "empty code point"
        raise PolicyError(msg)

    if len(text) == 1:
        return ord(text)

    lowered = text.lower()
    try:
        if lowered.startswith("u+") or lowered.startswith("0x"):
            code_point = int(text[2:], 16)
        else:
            code_point = int(text, 10)
    except ValueError as exc:
        msg = f"invalid code point: {value!r}"
        raise PolicyError(msg) from exc

    if not 0 <= code_point <= MAX_CODE_POINT:
        msg = f"code point outside Unicode range: {value!r}"
        raise PolicyError(msg)
    return code_point


def _split_range(value: str) -> tuple[str, str] | None:
    if ".." in value:
        left, right = value.split("..", 1)
        return left, right

    # Treat one literal hyphen as a single character, not as a range separator.
    if value == "-":
        return None

    if "-" not in value:
        return None

    # U+2010-U+2015, 0x20-0x7e, 32-126, or a-z.
    left, right = value.split("-", 1)
    if left and right:
        return left, right
    return None


@dataclass(frozen=True, slots=True)
class CharacterPolicy:
    """Allow/deny policy for Unicode characters.

    A character is disallowed when it is outside the configured allowlist or
    inside the configured denylist. Denylist rules take precedence over
    allowlist rules.
    """

    allowed_chars: frozenset[str]
    allowed_ranges: tuple[CodePointRange, ...]
    disallowed_chars: frozenset[str]
    disallowed_ranges: tuple[CodePointRange, ...]

    @classmethod
    def from_config(
        cls,
        *,
        allowed_chars: tuple[str, ...],
        allowed_ranges: tuple[str, ...],
        disallowed_chars: tuple[str, ...],
        disallowed_ranges: tuple[str, ...],
    ) -> CharacterPolicy:
        """Build a policy from config-friendly string values."""

        return cls(
            allowed_chars=_expand_chars(allowed_chars),
            allowed_ranges=tuple(CodePointRange.parse(item) for item in allowed_ranges),
            disallowed_chars=_expand_chars(disallowed_chars),
            disallowed_ranges=tuple(
                CodePointRange.parse(item) for item in disallowed_ranges
            ),
        )

    def is_allowed(self, char: str) -> bool:
        """Return whether ``char`` passes the policy."""

        if char in self.disallowed_chars or any(
            item.contains(char) for item in self.disallowed_ranges
        ):
            return False

        has_allow_rules = bool(self.allowed_chars or self.allowed_ranges)
        if not has_allow_rules:
            return True

        return char in self.allowed_chars or any(
            item.contains(char) for item in self.allowed_ranges
        )

    def violation_reason(self, char: str) -> str:
        """Return a short human-readable reason for a disallowed character."""

        if char in self.disallowed_chars or any(
            item.contains(char) for item in self.disallowed_ranges
        ):
            return "denied by policy"
        return "not allowed by policy"


def _expand_chars(values: tuple[str, ...]) -> frozenset[str]:
    chars: set[str] = set()
    for value in values:
        chars.update(value)
    return frozenset(chars)
