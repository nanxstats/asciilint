import os
from pathlib import Path

import pytest

from asciilint.policy import CharacterPolicy
from asciilint.scanner import (
    Discovery,
    discover_files,
    is_text_file,
    scan,
    scan_text_file,
)


def test_is_text_file_uses_zlib_algorithm(tmp_path: Path) -> None:
    text = tmp_path / "text.txt"
    text.write_text("hello π\n", encoding="utf-8")
    binary = tmp_path / "image.bin"
    binary.write_bytes(b"hello\x00world")
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")

    assert is_text_file(text)
    assert not is_text_file(binary)
    assert not is_text_file(empty)


def test_discover_files_prunes_gitignore_and_custom_ignore_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    (tmp_path / "custom.ignore").write_text("ignored-by-custom/\n", encoding="utf-8")
    ignored_directories = {
        tmp_path / "ignored-by-git",
        tmp_path / "ignored-by-custom",
    }
    for directory in ignored_directories:
        directory.mkdir()
        (directory / "nested").mkdir()
        (directory / "nested" / "bad.txt").write_text("é", encoding="utf-8")
    (tmp_path / "kept.txt").write_text("ok", encoding="utf-8")

    real_scandir = os.scandir

    def guarded_scandir(path: str | os.PathLike[str]):
        assert Path(path) not in ignored_directories
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)

    discovery = discover_files(
        (tmp_path,),
        base_dir=tmp_path,
        respect_gitignore=True,
        ignore_files=(Path("custom.ignore"),),
    )

    assert {path.name for path in discovery.files} == {
        ".gitignore",
        "custom.ignore",
        "kept.txt",
    }
    assert discovery.ignored_count == 2


def test_discover_files_respects_negated_directory_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitignore").write_text(
        "generated/*\n!generated/keep/\n", encoding="utf-8"
    )
    ignored_directory = tmp_path / "generated" / "drop"
    ignored_directory.mkdir(parents=True)
    (ignored_directory / "bad.txt").write_text("é", encoding="utf-8")
    kept_directory = tmp_path / "generated" / "keep"
    kept_directory.mkdir()
    (kept_directory / "good.txt").write_text("ok", encoding="utf-8")

    real_scandir = os.scandir

    def guarded_scandir(path: str | os.PathLike[str]):
        assert Path(path) != ignored_directory
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)

    discovery = discover_files(
        (tmp_path,),
        base_dir=tmp_path,
        respect_gitignore=True,
        ignore_files=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in discovery.files} == {
        ".gitignore",
        "generated/keep/good.txt",
    }
    assert discovery.ignored_count == 1


def test_scan_text_file_reports_utf8_errors(tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_bytes(b"caf\xe9\n")
    policy = CharacterPolicy.from_config(
        allowed_chars=(),
        allowed_ranges=("U+0000-U+007F",),
        disallowed_chars=(),
        disallowed_ranges=(),
    )

    finding, error = scan_text_file(path, policy=policy, max_issues_per_file=5)

    assert finding is None
    assert error is not None
    assert "not valid UTF-8" in error.message


def test_scan_emits_progress_callbacks(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_text("é\n", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    policy = CharacterPolicy.from_config(
        allowed_chars=(),
        allowed_ranges=("U+0000-U+007F",),
        disallowed_chars=(),
        disallowed_ranges=(),
    )
    discovered: list[tuple[int, int]] = []
    statuses: list[tuple[str, str]] = []

    def on_discovery(discovery: Discovery) -> None:
        discovered.append((discovery.candidates_count, len(discovery.files)))

    def on_status(status: str, path: Path) -> None:
        statuses.append((status, path.name))

    result = scan(
        (tmp_path,),
        base_dir=tmp_path,
        respect_gitignore=True,
        ignore_files=(),
        policy=policy,
        max_issues_per_file=5,
        on_discovery=on_discovery,
        on_status=on_status,
    )

    assert discovered == [(2, 2)]
    assert statuses == [("x", "bad.txt"), ("\u2713", "ok.txt")]
    assert result.statuses == ("x", "\u2713")
