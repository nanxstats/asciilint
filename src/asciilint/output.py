"""Terminal report formatting."""

from __future__ import annotations

from asciilint.scanner import ScanResult, relpath


def format_report(result: ScanResult) -> str:
    """Format a complete scan report."""

    lines: list[str] = []
    lines.append(f"> Checking characters in {result.base_dir.as_posix()}")
    lines.append(
        "Files found: "
        f"{result.discovery.candidates_count}, "
        f"{result.text_files_count} text, "
        f"{result.binary_files_count} binary skipped, "
        f"{result.discovery.ignored_count} ignored"
    )
    if result.statuses:
        lines.append(f"Checking text: {''.join(result.statuses)}")
    else:
        lines.append("Checking text: none")

    if not result.has_issues:
        lines.append("No issues :-)")
        return "\n".join(lines)

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


def _describe_char(char: str) -> str:
    escaped = char.encode("unicode_escape").decode("ascii")
    if char == " ":
        escaped = "space"
    return f'U+{ord(char):04X} "{escaped}"'
