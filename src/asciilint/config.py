"""Configuration loading for asciilint."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_RANGES = ("U+0000-U+007F",)
DEFAULT_IGNORE_FILES = (Path(".asciilintignore"),)
CONFIG_FILE_NAME = "asciilint.toml"
CONFIG_TABLE = "asciilint"


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for a scan."""

    paths: tuple[Path, ...] = (Path("."),)
    respect_gitignore: bool = True
    ignore_files: tuple[Path, ...] = DEFAULT_IGNORE_FILES
    allowed_chars: tuple[str, ...] = ()
    allowed_ranges: tuple[str, ...] = DEFAULT_ALLOWED_RANGES
    disallowed_chars: tuple[str, ...] = ()
    disallowed_ranges: tuple[str, ...] = ()
    max_issues_per_file: int = 5

    @classmethod
    def default(cls) -> Config:
        """Return the default configuration."""

        return cls()

    @classmethod
    def load(cls, path: Path) -> Config:
        """Load configuration from a TOML file."""

        try:
            with path.open("rb") as file:
                raw = tomllib.load(file)
        except OSError as exc:
            msg = f"could not read config file {path}: {exc}"
            raise ConfigError(msg) from exc
        except tomllib.TOMLDecodeError as exc:
            msg = f"invalid TOML in config file {path}: {exc}"
            raise ConfigError(msg) from exc

        table = raw.get(CONFIG_TABLE, raw)
        if not isinstance(table, dict):
            msg = f"config table [{CONFIG_TABLE}] must be a table"
            raise ConfigError(msg)

        return cls.default().update_from_mapping(table, source=path)

    def update_from_mapping(self, data: dict[str, Any], *, source: Path) -> Config:
        """Return a copy updated from TOML data."""

        allowed_keys = {
            "paths",
            "respect_gitignore",
            "ignore_files",
            "allowed_chars",
            "allowed_ranges",
            "disallowed_chars",
            "disallowed_ranges",
            "max_issues_per_file",
        }
        unknown = sorted(set(data) - allowed_keys)
        if unknown:
            msg = f"unknown config key(s) in {source}: {', '.join(unknown)}"
            raise ConfigError(msg)

        updated = self
        if "paths" in data:
            updated = replace(
                updated, paths=_path_tuple(data["paths"], key="paths", source=source)
            )
        if "respect_gitignore" in data:
            updated = replace(
                updated,
                respect_gitignore=_bool(
                    data["respect_gitignore"], key="respect_gitignore", source=source
                ),
            )
        if "ignore_files" in data:
            updated = replace(
                updated,
                ignore_files=_path_tuple(
                    data["ignore_files"], key="ignore_files", source=source
                ),
            )
        if "allowed_chars" in data:
            updated = replace(
                updated,
                allowed_chars=_str_tuple(
                    data["allowed_chars"], key="allowed_chars", source=source
                ),
            )
        if "allowed_ranges" in data:
            updated = replace(
                updated,
                allowed_ranges=_str_tuple(
                    data["allowed_ranges"], key="allowed_ranges", source=source
                ),
            )
        if "disallowed_chars" in data:
            updated = replace(
                updated,
                disallowed_chars=_str_tuple(
                    data["disallowed_chars"], key="disallowed_chars", source=source
                ),
            )
        if "disallowed_ranges" in data:
            updated = replace(
                updated,
                disallowed_ranges=_str_tuple(
                    data["disallowed_ranges"], key="disallowed_ranges", source=source
                ),
            )
        if "max_issues_per_file" in data:
            max_issues = data["max_issues_per_file"]
            if not isinstance(max_issues, int) or max_issues < 1:
                msg = f"{source}: max_issues_per_file must be a positive integer"
                raise ConfigError(msg)
            updated = replace(updated, max_issues_per_file=max_issues)

        return updated


def find_config(start: Path) -> Path | None:
    """Find ``asciilint.toml`` in ``start`` or its parents."""

    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILE_NAME
        if candidate.is_file():
            return candidate
    return None


def _str_tuple(value: object, *, key: str, source: Path) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    msg = f"{source}: {key} must be a string or a list of strings"
    raise ConfigError(msg)


def _path_tuple(value: object, *, key: str, source: Path) -> tuple[Path, ...]:
    return tuple(Path(item) for item in _str_tuple(value, key=key, source=source))


def _bool(value: object, *, key: str, source: Path) -> bool:
    if isinstance(value, bool):
        return value
    msg = f"{source}: {key} must be true or false"
    raise ConfigError(msg)
