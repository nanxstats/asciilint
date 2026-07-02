"""Terminal report formatting."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from asciilint.scanner import Discovery, ScanResult, relpath


class ProgressReporter:
    """Write scan progress as files are discovered and checked."""

    def __init__(
        self, write: Callable[[str], None], *, status_line_width: int = 80
    ) -> None:
        if status_line_width < 1:
            msg = "status_line_width must be positive"
            raise ValueError(msg)

        self._write = write
        self._status_line_width = status_line_width
        self._status_label = "Checking text:"
        self._status_line_started = False
        self._statuses_on_current_line = 0
        self._finished = False

    def start(self, base_dir: Path) -> None:
        """Write the initial scan line."""

        self._write(f"{format_scan_start(base_dir)}\n")

    def discovery(self, discovery: Discovery) -> None:
        """Write the discovery summary before per-file scanning begins."""

        self._write(f"{format_discovery_progress(discovery)}\n")

    def status(self, status: str) -> None:
        """Write one text-file status character."""

        if self._finished:
            msg = "cannot write progress after finish()"
            raise RuntimeError(msg)

        if not self._status_line_started:
            self._write(f"{self._status_label}\n")
            self._status_line_started = True

        self._write(status)
        self._statuses_on_current_line += 1

        if self._statuses_on_current_line == self._status_line_width:
            self._write("\n")
            self._statuses_on_current_line = 0

    def finish(self) -> None:
        """Finish the status line, reporting ``none`` when no text was checked."""

        if self._finished:
            return

        if not self._status_line_started:
            self._write(f"{self._status_label} none\n")
        elif self._statuses_on_current_line:
            self._write("\n")

        self._finished = True


def format_scan_start(base_dir: Path) -> str:
    """Format the initial scan line."""

    return f"> Checking characters in {base_dir.as_posix()}"


def format_discovery_progress(discovery: Discovery) -> str:
    """Format a discovery summary that is known before scanning starts."""

    return (
        "Files found: "
        f"{discovery.candidates_count}, "
        f"{len(discovery.files)} to scan, "
        f"{discovery.ignored_count} ignored"
    )


def format_scan_totals(result: ScanResult) -> str:
    """Format a final file-kind summary after scanning finishes."""

    return (
        "Files checked: "
        f"{result.text_files_count} text, "
        f"{result.binary_files_count} binary skipped, "
        f"{len(result.errors)} read error(s)"
    )


def format_report(result: ScanResult, *, include_scan_details: bool = True) -> str:
    """Format a complete scan report."""

    lines: list[str] = []
    if include_scan_details:
        lines.append(format_scan_start(result.base_dir))
        lines.append(_format_final_file_summary(result))
        if result.statuses:
            lines.append("Checking text:")
            lines.extend(_status_chunks(result.statuses, width=80))
        else:
            lines.append("Checking text: none")

    if not result.has_issues:
        lines.append("No issues :-)")
        return "\n".join(lines)

    if include_scan_details:
        lines.append("")
    lines.append("Issues :-(")

    if result.findings:
        lines.append("> Disallowed characters")
        for index, finding in enumerate(result.findings, start=1):
            path = relpath(finding.path, result.base_dir)
            lines.append(f"  {index}. {path}")
            for issue_index, issue in enumerate(finding.issues, start=1):
                lines.append(
                    "     "
                    f"{issue_index}. [L{issue.line:03}:C{issue.column:03}] "
                    f"{_describe_char(issue.char)} {issue.reason}"
                )
            if finding.truncated:
                remaining = finding.total_issues - len(finding.issues)
                lines.append(f"     ... and {remaining} more issue(s)")

    if result.errors:
        lines.append("> Read errors")
        for index, error in enumerate(result.errors, start=1):
            path = relpath(error.path, result.base_dir)
            lines.append(f"  {index}. {path}: {error.message}")

    lines.append(
        "Summary: "
        f"{result.total_policy_issues} disallowed character(s), "
        f"{len(result.errors)} read error(s)"
    )
    return "\n".join(lines)


def _format_final_file_summary(result: ScanResult) -> str:
    return (
        "Files found: "
        f"{result.discovery.candidates_count}, "
        f"{result.text_files_count} text, "
        f"{result.binary_files_count} binary skipped, "
        f"{result.discovery.ignored_count} ignored"
    )


def _status_chunks(statuses: tuple[str, ...], *, width: int) -> list[str]:
    joined = "".join(statuses)
    return [joined[index : index + width] for index in range(0, len(joined), width)]


def _describe_char(char: str) -> str:
    escaped = char.encode("unicode_escape").decode("ascii")
    if char == " ":
        escaped = "space"
    return f'U+{ord(char):04X} "{escaped}"'
