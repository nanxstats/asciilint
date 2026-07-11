"""File discovery and scanning."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
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
    """File discovery result.

    ``candidates_count`` counts file entries only. ``ignored_count`` counts
    ignored file entries and each pruned directory once.
    """

    files: tuple[Path, ...]
    candidates_count: int
    ignored_count: int
    ignore_sources: tuple[IgnoreSource, ...]


@dataclass(frozen=True, slots=True)
class _DiscoveryEntry:
    """One file or pruned directory found during traversal."""

    path: Path
    ignored: bool
    is_directory: bool


DiscoveryCallback = Callable[[Discovery], None]
StatusCallback = Callable[[str, Path], None]


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
    """Discover files while pruning gitignore-style directory matches."""

    ignore_sources = _load_ignore_sources(
        base_dir=base_dir,
        respect_gitignore=respect_gitignore,
        ignore_files=ignore_files,
    )
    entries = tuple(
        _dedupe_entries(_iter_discovery_entries(paths, ignore_sources=ignore_sources))
    )
    files = tuple(entry.path for entry in entries if not entry.ignored)
    candidates_count = sum(not entry.is_directory for entry in entries)
    ignored_count = sum(entry.ignored for entry in entries)
    return Discovery(
        files=files,
        candidates_count=candidates_count,
        ignored_count=ignored_count,
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
    on_discovery: DiscoveryCallback | None = None,
    on_status: StatusCallback | None = None,
) -> ScanResult:
    """Discover and scan text files."""

    discovery = discover_files(
        paths,
        base_dir=base_dir,
        respect_gitignore=respect_gitignore,
        ignore_files=ignore_files,
    )
    if on_discovery is not None:
        on_discovery(discovery)

    findings: list[FileFinding] = []
    errors: list[FileError] = []
    statuses: list[str] = []
    text_count = 0
    binary_count = 0

    def record_status(status: str, path: Path) -> None:
        statuses.append(status)
        if on_status is not None:
            on_status(status, path)

    for path in discovery.files:
        try:
            if not is_text_file(path):
                binary_count += 1
                continue
        except OSError as exc:
            errors.append(FileError(path=path, message=str(exc)))
            record_status("?", path)
            continue

        text_count += 1
        finding, error = scan_text_file(
            path, policy=policy, max_issues_per_file=max_issues_per_file
        )
        if error is not None:
            errors.append(error)
            record_status("?", path)
        elif finding is not None:
            findings.append(finding)
            record_status("x", path)
        else:
            record_status("\u2713", path)

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


def _iter_discovery_entries(
    paths: Iterable[Path], *, ignore_sources: tuple[IgnoreSource, ...]
) -> Iterable[_DiscoveryEntry]:
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            if _is_ignored(path, ignore_sources, is_dir=True):
                yield _DiscoveryEntry(path=path, ignored=True, is_directory=True)
            else:
                yield from _walk_entries(path, ignore_sources=ignore_sources)
        elif path.is_file():
            yield _DiscoveryEntry(
                path=path,
                ignored=_is_ignored(path, ignore_sources, is_dir=False),
                is_directory=False,
            )


def _walk_entries(
    root: Path, *, ignore_sources: tuple[IgnoreSource, ...]
) -> Iterable[_DiscoveryEntry]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current_dir = Path(dirpath)
        kept_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            path = current_dir / dirname
            if _is_ignored(path, ignore_sources, is_dir=True):
                yield _DiscoveryEntry(path=path, ignored=True, is_directory=True)
            elif not path.is_symlink():
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        for filename in sorted(filenames):
            path = current_dir / filename
            if _is_ignored(path, ignore_sources, is_dir=False):
                yield _DiscoveryEntry(path=path, ignored=True, is_directory=False)
                continue
            if path.is_file():
                yield _DiscoveryEntry(
                    path=path.resolve(), ignored=False, is_directory=False
                )


def _dedupe_entries(entries: Iterable[_DiscoveryEntry]) -> Iterable[_DiscoveryEntry]:
    seen: set[Path] = set()
    for entry in entries:
        if entry.path in seen:
            continue
        seen.add(entry.path)
        yield entry


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


def _is_ignored(
    path: Path, ignore_sources: tuple[IgnoreSource, ...], *, is_dir: bool
) -> bool:
    for source in ignore_sources:
        # An ignore file does not exclude itself through its own patterns.
        if path == source.path:
            continue
        try:
            relative = path.relative_to(source.base_dir)
        except ValueError:
            continue
        if relative == Path("."):
            continue

        match_path = relative.as_posix()
        if is_dir:
            match_path += "/"
        if source.spec.match_file(match_path):
            return True

    return False
