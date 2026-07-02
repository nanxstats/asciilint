# Changelog

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
