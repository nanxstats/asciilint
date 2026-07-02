"""File discovery and scanning."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pathspec import PathSpec  # type: ignore[import-untyped]

from asciilint.policy import CharacterPolicy

TEXT_BYTES = frozenset({9, 10, 13, *range(32, 256)})
BINARY_BYTES = frozenset({*range(0, 7), *range(14, 32)})
BUILTIN_IGNORE_PATTERNS = (".git/", ".hg/", ".svn/")


@dataclass(frozen=True, slots=True)
class IgnoreSource:
    """Loaded ignore file and its compiled pathspec."""

    path: Path
    base_dir: Path
    spec: PathSpec


@dataclass(frozen=True, slots=True)
class Discovery:
    """File discovery result."""

    files: tuple[Path, ...]
    candidates_count: int
    ignored_count: int
    ignore_sources: tuple[IgnoreSource, ...]


@dataclass(frozen=True, slots=True)
class CharacterIssue:
    """One disallowed character occurrence."""

    line: int
    column: int
    char: str
    reason: str


@dataclass(frozen=True, slots=True)
class FileFinding:
    """Policy findings for one file."""

    path: Path
    issues: tuple[CharacterIssue, ...]
    total_issues: int

    @property
    def truncated(self) -> bool:
        """Return whether only a prefix of issues is stored."""

        return self.total_issues > len(self.issues)


@dataclass(frozen=True, slots=True)
class FileError:
    """A file that could not be decoded or read."""

    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Complete scan result."""

    base_dir: Path
    discovery: Discovery
    text_files_count: int
    binary_files_count: int
    findings: tuple[FileFinding, ...]
    errors: tuple[FileError, ...]
    statuses: tuple[str, ...]

    @property
    def has_issues(self) -> bool:
        """Return whether this scan should fail CI."""

        return bool(self.findings or self.errors)

    @property
    def total_policy_issues(self) -> int:
        """Return the number of policy violations found."""

        return sum(finding.total_issues for finding in self.findings)


def is_text_file(path: Path, *, bytes_to_read: int | None = None) -> bool:
    """Classify a file as text or binary with the zlib txtvsbin algorithm."""

    with path.open("rb") as file:
        data = file.read() if bytes_to_read is None else file.read(bytes_to_read)

    if not data:
        return False

    has_text_byte = any(byte in TEXT_BYTES for byte in data)
    has_binary_byte = any(byte in BINARY_BYTES for byte in data)
    return has_text_byte and not has_binary_byte


def discover_files(
    paths: Iterable[Path],
    *,
    base_dir: Path,
    respect_gitignore: bool,
    ignore_files: tuple[Path, ...],
) -> Discovery:
    """Discover files and apply gitignore-style filters in batches."""

    candidate_files = tuple(_dedupe(_iter_candidate_files(paths)))
    ignore_sources = _load_ignore_sources(
        base_dir=base_dir,
        respect_gitignore=respect_gitignore,
        ignore_files=ignore_files,
    )
    ignored = _match_ignored(candidate_files, ignore_sources, base_dir=base_dir)
    files = tuple(path for path in candidate_files if path not in ignored)
    return Discovery(
        files=files,
        candidates_count=len(candidate_files),
        ignored_count=len(ignored),
        ignore_sources=ignore_sources,
    )


def scan(
    paths: Iterable[Path],
    *,
    base_dir: Path,
    respect_gitignore: bool,
    ignore_files: tuple[Path, ...],
    policy: CharacterPolicy,
    max_issues_per_file: int,
) -> ScanResult:
    """Discover and scan text files."""

    discovery = discover_files(
        paths,
        base_dir=base_dir,
        respect_gitignore=respect_gitignore,
        ignore_files=ignore_files,
    )

    findings: list[FileFinding] = []
    errors: list[FileError] = []
    statuses: list[str] = []
    text_count = 0
    binary_count = 0

    for path in discovery.files:
        try:
            if not is_text_file(path):
                binary_count += 1
                continue
        except OSError as exc:
            errors.append(FileError(path=path, message=str(exc)))
            statuses.append("?")
            continue

        text_count += 1
        finding, error = scan_text_file(
            path, policy=policy, max_issues_per_file=max_issues_per_file
        )
        if error is not None:
            errors.append(error)
            statuses.append("?")
        elif finding is not None:
            findings.append(finding)
            statuses.append("x")
        else:
            statuses.append("\u2713")

    return ScanResult(
        base_dir=base_dir,
        discovery=discovery,
        text_files_count=text_count,
        binary_files_count=binary_count,
        findings=tuple(findings),
        errors=tuple(errors),
        statuses=tuple(statuses),
    )


def scan_text_file(
    path: Path, *, policy: CharacterPolicy, max_issues_per_file: int
) -> tuple[FileFinding | None, FileError | None]:
    """Scan one UTF-8 text file for policy violations."""

    issues: list[CharacterIssue] = []
    total_issues = 0

    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                for column, char in enumerate(line, start=1):
                    if policy.is_allowed(char):
                        continue
                    total_issues += 1
                    if len(issues) < max_issues_per_file:
                        issues.append(
                            CharacterIssue(
                                line=line_number,
                                column=column,
                                char=char,
                                reason=policy.violation_reason(char),
                            )
                        )
    except UnicodeDecodeError as exc:
        return None, FileError(
            path=path,
            message=(
                "not valid UTF-8; convert this file to UTF-8 before running "
                f"asciilint ({exc})"
            ),
        )
    except OSError as exc:
        return None, FileError(path=path, message=str(exc))

    if total_issues == 0:
        return None, None
    return FileFinding(path=path, issues=tuple(issues), total_issues=total_issues), None


def relpath(path: Path, base_dir: Path) -> str:
    """Return a stable POSIX-style path relative to ``base_dir`` when possible."""

    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path, base_dir).replace(os.sep, "/")


def _iter_candidate_files(paths: Iterable[Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            yield from _walk_files(path)
        elif path.is_file():
            yield path


def _walk_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if not (Path(dirpath) / dirname).is_symlink()
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.is_file():
                yield path.resolve()


def _dedupe(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        yield path


def _load_ignore_sources(
    *, base_dir: Path, respect_gitignore: bool, ignore_files: tuple[Path, ...]
) -> tuple[IgnoreSource, ...]:
    sources: list[IgnoreSource] = [
        IgnoreSource(
            path=base_dir / "<builtin>",
            base_dir=base_dir.resolve(),
            spec=PathSpec.from_lines("gitignore", BUILTIN_IGNORE_PATTERNS),
        )
    ]

    files: list[Path] = []
    if respect_gitignore:
        files.append(base_dir / ".gitignore")
    files.extend(ignore_files)

    for raw_path in files:
        path = raw_path if raw_path.is_absolute() else base_dir / raw_path
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        sources.append(
            IgnoreSource(
                path=path.resolve(),
                base_dir=path.parent.resolve(),
                spec=PathSpec.from_lines("gitignore", lines),
            )
        )

    return tuple(sources)


def _match_ignored(
    files: tuple[Path, ...], ignore_sources: tuple[IgnoreSource, ...], *, base_dir: Path
) -> frozenset[Path]:
    ignored: set[Path] = set()
    base_dir = base_dir.resolve()

    for source in ignore_sources:
        rel_to_path: dict[str, Path] = {}
        for path in files:
            try:
                rel = path.resolve().relative_to(source.base_dir)
            except ValueError:
                continue
            rel_to_path[rel.as_posix()] = path

        for matched in source.spec.match_files(rel_to_path):
            path = rel_to_path[matched]
            # Never ignore explicitly provided ignore files outside normal trees.
            if path == source.path or path == base_dir / "<builtin>":
                continue
            ignored.add(path)

    return frozenset(ignored)
