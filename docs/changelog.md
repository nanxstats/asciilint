# Changelog

## asciilint 0.3.0

### Improvements

- Refactored file discovery logic to load ignore rules before walking the
  filesystem and prune matching directories from `os.walk` (#12).

  Previously, `asciilint` enumerated every file before applying ignore rules,
  which caused noticeable startup lag in projects containing large ignored
  trees such as `.venv/` and `node_modules/`.
  Their contents are now never queried, while configured ignore files,
  negated directory rules, and `--no-gitignore` behavior remain supported.

## asciilint 0.2.1

### Dependencies

- Lower the minimum required version of `click` to 8.3.0 and
  `pathspec` to 1.0.0 to allow for more flexible dependency resolution
  in downstream projects (#9).

## asciilint 0.2.0

### Improvements

- Added progressive CLI output that prints scan setup, discovery counts, and
  per-file status marks while scanning instead of waiting for the full scan to
  finish (#5).
- Wrapped long status mark output at a fixed width with marks starting on their
  own lines, to keep large-project and GitHub Actions logs responsive and
  readable (#5).
- Added scanner progress callbacks so the CLI can stream progress while
  preserving the existing complete scan result for final reporting (#5).

## asciilint 0.1.0

### New features

- Added the `asciilint` command-line interface for recursively scanning projects
  for disallowed characters in UTF-8 text files.
- Added ASCII-only defaults to detect non-ASCII characters with no required
  configuration.
- Added configurable character policies with arbitrary allowed and disallowed
  literal characters and Unicode code point ranges.
- Added `asciilint.toml` support, parsed with `tomllib`, plus equivalent
  command line options for CI usage.
- Added gitignore-syntax file filtering with `pathspec`, including
  `.gitignore`, `.asciilintignore`, and user-specified ignore files.
- Added automatic binary file skipping using the zlib `txtvsbin` heuristic.
- Added explicit reporting for files that look like text but are not valid UTF-8.
- Added concise terminal output with file, line, column, code point, and
  summary information suitable for local use and CI logs.
- Added project documentation and pytest coverage for CLI behavior,
  policy parsing, ignore handling, binary detection, and UTF-8 errors.
