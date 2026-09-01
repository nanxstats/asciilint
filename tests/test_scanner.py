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
    ansi_log = tmp_path / "colored.log"
    ansi_log.write_bytes(b"\x1b[31merror\x1b[0m\n")
    gray_only = tmp_path / "gray.bin"
    gray_only.write_bytes(b"\x1a\x1b")

    assert is_text_file(text)
    assert not is_text_file(binary)
    assert not is_text_file(empty)
    # SUB and ESC are gray-listed as in zlib's detect_data_type: tolerated
    # alongside text, but not text on their own.
    assert is_text_file(ansi_log)
    assert not is_text_file(gray_only)


def test_is_text_file_detects_binary_signatures(tmp_path: Path) -> None:
    # Uncompressed PDFs (for example, written by R's pdf() device) can contain
    # only allow-listed bytes, so txtvsbin alone would classify them as text.
    pdf = tmp_path / "figure.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%\x81\xe2\x81\xe3\x81\xcf\x81\xd3\\r\n1 0 obj\n")
    assert not is_text_file(pdf)

    # The signature applies regardless of file extension.
    renamed_pdf = tmp_path / "figure"
    renamed_pdf.write_bytes(b"%PDF-1.4\nplain ascii body\n")
    assert not is_text_file(renamed_pdf)

    dos_eps = tmp_path / "figure.eps"
    dos_eps.write_bytes(b"\xc5\xd0\xd3\xc6" + b"preview bytes")
    assert not is_text_file(dos_eps)

    # The signature only matches at offset 0, not later in the file.
    mentions_pdf = tmp_path / "notes.txt"
    mentions_pdf.write_text("PDF files start with %PDF-1.4\n", encoding="utf-8")
    assert is_text_file(mentions_pdf)


def test_is_text_file_samples_head_and_tail_of_large_files(tmp_path: Path) -> None:
    sample_size = 8

    tail_binary = tmp_path / "tail.bin"
    tail_binary.write_bytes(b"a" * 100 + b"\x00")
    assert not is_text_file(tail_binary, sample_size=sample_size)

    head_binary = tmp_path / "head.bin"
    head_binary.write_bytes(b"\x00" + b"a" * 100)
    assert not is_text_file(head_binary, sample_size=sample_size)

    # A binary byte hidden between the sampled head and tail is not seen.
    middle_binary = tmp_path / "middle.bin"
    middle_binary.write_bytes(b"a" * 50 + b"\x00" + b"a" * 50)
    assert is_text_file(middle_binary, sample_size=sample_size)

    # Files up to twice the sample size are read fully.
    small_middle_binary = tmp_path / "small-middle.bin"
    small_middle_binary.write_bytes(b"a" * 7 + b"\x00" + b"a" * 8)
    assert not is_text_file(small_middle_binary, sample_size=sample_size)


def test_scan_text_file_positions_are_stable_across_chunks(tmp_path: Path) -> None:
    path = tmp_path / "chunked.txt"
    path.write_text("abc\né\nxyé\naaaaaé\n", encoding="utf-8")
    policy = CharacterPolicy.from_config(
        allowed_chars=(),
        allowed_ranges=("U+0000-U+007F",),
        disallowed_chars=(),
        disallowed_ranges=(),
    )

    expected = [(2, 1), (3, 3), (4, 6)]
    for chunk_size in (1, 2, 3, 4, 1024):
        finding, error = scan_text_file(
            path, policy=policy, max_issues_per_file=5, chunk_size=chunk_size
        )

        assert error is None
        assert finding is not None
        assert finding.total_issues == 3
        assert [(issue.line, issue.column) for issue in finding.issues] == expected, (
            f"chunk_size={chunk_size}"
        )


def test_scan_text_file_counts_issues_beyond_the_stored_limit(tmp_path: Path) -> None:
    path = tmp_path / "many.txt"
    path.write_text("é" * 10, encoding="utf-8")
    policy = CharacterPolicy.from_config(
        allowed_chars=(),
        allowed_ranges=("U+0000-U+007F",),
        disallowed_chars=(),
        disallowed_ranges=(),
    )

    finding, error = scan_text_file(
        path, policy=policy, max_issues_per_file=3, chunk_size=4
    )

    assert error is None
    assert finding is not None
    assert finding.total_issues == 10
    assert len(finding.issues) == 3
    assert finding.truncated
    assert [(issue.line, issue.column) for issue in finding.issues] == [
        (1, 1),
        (1, 2),
        (1, 3),
    ]


def test_discover_files_prunes_gitignore_and_custom_ignore_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitignore").write_text(
        "ignored-by-git/\nignored-file.txt\n", encoding="utf-8"
    )
    (tmp_path / "custom.ignore").write_text("ignored-by-custom/\n", encoding="utf-8")
    ignored_directories = {
        tmp_path / "ignored-by-git",
        tmp_path / "ignored-by-custom",
    }
    for directory in ignored_directories:
        directory.mkdir()
        (directory / "nested").mkdir()
        (directory / "nested" / "bad.txt").write_text("é", encoding="utf-8")
    (tmp_path / "ignored-file.txt").write_text("é", encoding="utf-8")
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
    assert discovery.candidates_count == 4
    assert discovery.ignored_count == 3


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
    assert discovery.candidates_count == 2
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
