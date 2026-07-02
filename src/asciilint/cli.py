"""Command-line interface for asciilint."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import click

from asciilint import __version__
from asciilint.config import Config, ConfigError, find_config
from asciilint.output import format_report
from asciilint.policy import CharacterPolicy, PolicyError
from asciilint.scanner import scan


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(path_type=Path, exists=True),
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    help="Path to asciilint.toml. By default, asciilint searches upward.",
)
@click.option(
    "--no-config",
    is_flag=True,
    help="Do not load asciilint.toml.",
)
@click.option(
    "--ignore-file",
    "ignore_files",
    multiple=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Additional gitignore-syntax ignore file. Can be used more than once.",
)
@click.option(
    "--no-gitignore",
    is_flag=True,
    help="Do not read .gitignore.",
)
@click.option(
    "--allow-any",
    is_flag=True,
    help="Disable the default ASCII allowlist before applying allow/deny options.",
)
@click.option(
    "--allowed-char",
    multiple=True,
    help="Allowed literal character(s). Can be used more than once.",
)
@click.option(
    "--allowed-range",
    multiple=True,
    metavar="RANGE",
    help="Allowed code point range, e.g. U+0000-U+007F or U+2010-U+2015.",
)
@click.option(
    "--disallowed-char",
    multiple=True,
    help="Disallowed literal character(s). Can be used more than once.",
)
@click.option(
    "--disallowed-range",
    multiple=True,
    metavar="RANGE",
    help="Disallowed code point range. Deny rules take precedence.",
)
@click.option(
    "--max-issues-per-file",
    type=click.IntRange(min=1),
    help="Maximum example issues to print per file.",
)
def main(
    paths: tuple[Path, ...],
    config_path: Path | None,
    no_config: bool,
    ignore_files: tuple[Path, ...],
    no_gitignore: bool,
    allow_any: bool,
    allowed_char: tuple[str, ...],
    allowed_range: tuple[str, ...],
    disallowed_char: tuple[str, ...],
    disallowed_range: tuple[str, ...],
    max_issues_per_file: int | None,
) -> None:
    """Scan text files for non-ASCII or custom-disallowed characters."""

    try:
        config = _build_config(
            paths=paths,
            config_path=config_path,
            no_config=no_config,
            ignore_files=ignore_files,
            no_gitignore=no_gitignore,
            allow_any=allow_any,
            allowed_char=allowed_char,
            allowed_range=allowed_range,
            disallowed_char=disallowed_char,
            disallowed_range=disallowed_range,
            max_issues_per_file=max_issues_per_file,
        )
        policy = CharacterPolicy.from_config(
            allowed_chars=config.allowed_chars,
            allowed_ranges=config.allowed_ranges,
            disallowed_chars=config.disallowed_chars,
            disallowed_ranges=config.disallowed_ranges,
        )
    except (ConfigError, PolicyError) as exc:
        raise click.ClickException(str(exc)) from exc

    base_dir = _scan_base_dir(config.paths)
    result = scan(
        config.paths,
        base_dir=base_dir,
        respect_gitignore=config.respect_gitignore,
        ignore_files=config.ignore_files,
        policy=policy,
        max_issues_per_file=config.max_issues_per_file,
    )
    click.echo(format_report(result))
    if result.has_issues:
        raise click.exceptions.Exit(1)


def _build_config(
    *,
    paths: tuple[Path, ...],
    config_path: Path | None,
    no_config: bool,
    ignore_files: tuple[Path, ...],
    no_gitignore: bool,
    allow_any: bool,
    allowed_char: tuple[str, ...],
    allowed_range: tuple[str, ...],
    disallowed_char: tuple[str, ...],
    disallowed_range: tuple[str, ...],
    max_issues_per_file: int | None,
) -> Config:
    config = Config.default()

    if not no_config:
        discovered = config_path or find_config(Path.cwd())
        if discovered is not None:
            config = Config.load(discovered)

    if paths:
        config = replace(config, paths=paths)
    if no_gitignore:
        config = replace(config, respect_gitignore=False)
    if ignore_files:
        config = replace(config, ignore_files=(*config.ignore_files, *ignore_files))
    if allow_any:
        config = replace(config, allowed_chars=(), allowed_ranges=())
    if allowed_char:
        config = replace(config, allowed_chars=(*config.allowed_chars, *allowed_char))
    if allowed_range:
        config = replace(
            config, allowed_ranges=(*config.allowed_ranges, *allowed_range)
        )
    if disallowed_char:
        config = replace(
            config, disallowed_chars=(*config.disallowed_chars, *disallowed_char)
        )
    if disallowed_range:
        config = replace(
            config, disallowed_ranges=(*config.disallowed_ranges, *disallowed_range)
        )
    if max_issues_per_file is not None:
        config = replace(config, max_issues_per_file=max_issues_per_file)

    return config


def _scan_base_dir(paths: tuple[Path, ...]) -> Path:
    resolved_dirs = []
    for path in paths:
        resolved = path.resolve()
        resolved_dirs.append(resolved if resolved.is_dir() else resolved.parent)
    if not resolved_dirs:
        return Path.cwd().resolve()
    if len(resolved_dirs) == 1:
        return resolved_dirs[0]
    return Path(os.path.commonpath([str(path) for path in resolved_dirs])).resolve()
