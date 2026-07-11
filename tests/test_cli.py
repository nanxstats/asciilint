from pathlib import Path

from click.testing import CliRunner

from asciilint.cli import main


def test_cli_passes_ascii_project(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("hello\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", str(tmp_path)])

    assert result.exit_code == 0
    assert "No issues :-)" in result.output
    assert "Checking text:\n✓\n" in result.output
    assert "Files checked: 1 text, 0 binary skipped, 0 read error(s)" in result.output


def test_cli_fails_on_non_ascii_by_default(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_text("café\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", str(tmp_path)])

    assert result.exit_code == 1
    assert "Issues :-(" in result.output
    assert "> Disallowed characters" in result.output
    assert "bad.txt" in result.output
    assert 'U+00E9 "\\xe9" not allowed by policy' in result.output


def test_cli_respects_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "bad.txt").write_text("é\n", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", str(tmp_path)])

    assert result.exit_code == 0
    assert "Files found: 2, 2 to scan, 1 ignored" in result.output
    assert "No issues :-)" in result.output


def test_cli_no_gitignore_scans_gitignored_directory(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "bad.txt").write_text("é\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", "--no-gitignore", str(tmp_path)])

    assert result.exit_code == 1
    assert "ignored/bad.txt" in result.output


def test_cli_prunes_directory_from_additional_ignore_file(tmp_path: Path) -> None:
    ignore_file = tmp_path / "custom.ignore"
    ignore_file.write_text("generated/\n", encoding="utf-8")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "bad.txt").write_text("é\n", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--no-config",
            "--no-gitignore",
            "--ignore-file",
            str(ignore_file),
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "1 ignored" in result.output
    assert "No issues :-)" in result.output


def test_cli_wraps_progress_statuses_for_ci_logs(tmp_path: Path) -> None:
    for index in range(82):
        (tmp_path / f"ok-{index:03}.txt").write_text("ok\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", str(tmp_path)])

    assert result.exit_code == 0
    assert "Checking text:\n" + ("\u2713" * 80) + "\n" in result.output
    assert ("\u2713" * 80) + "\n" + ("\u2713" * 2) + "\n" in result.output
    assert "No issues :-)" in result.output


def test_cli_uses_config_for_arbitrary_policy(tmp_path: Path) -> None:
    (tmp_path / "asciilint.toml").write_text(
        """
[asciilint]
allowed_ranges = ["U+0000-U+00FF"]
disallowed_chars = ["é"]
max_issues_per_file = 2
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "text.txt").write_text("café\nπ\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main, ["--config", str(tmp_path / "asciilint.toml"), str(tmp_path)]
    )

    assert result.exit_code == 1
    assert 'U+00E9 "\\xe9" denied by policy' in result.output
    assert 'U+03C0 "\\u03c0" not allowed by policy' in result.output


def test_cli_allow_any_with_denylist(tmp_path: Path) -> None:
    (tmp_path / "text.txt").write_text("emoji ✅ and x\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--no-config", "--allow-any", "--disallowed-char", "x", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert 'U+0078 "x" denied by policy' in result.output
    assert "U+2705" not in result.output


def test_cli_reports_non_utf8_text_file(tmp_path: Path) -> None:
    (tmp_path / "latin1.txt").write_bytes(b"caf\xe9\n")
    runner = CliRunner()

    result = runner.invoke(main, ["--no-config", str(tmp_path)])

    assert result.exit_code == 1
    assert "> Read errors" in result.output
    assert "not valid UTF-8" in result.output
