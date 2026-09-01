# Changelog

## asciilint (development version)

### Improvements

- Files starting with a known binary format signature are now correctly
  classified as binary before the txtvsbin byte set check runs (#23).
  This covers formats whose content can contain entirely of allow-listed bytes:
  PDF files (for example, uncompressed PDFs written by R's `pdf()` device)
  and DOS EPS binary files (EPS with a TIFF/WMF preview).
  Previously, such files were classified as text files and then reported as
  UTF-8 read errors.
- Aligned binary file detection with the zlib C implementation of the
  txtvsbin algorithm (#22). Bytes 26 (SUB) and 27 (ESC) are now gray-listed
  (tolerated) instead of block-listed. This matches the mask in zlib's
  `detect_data_type`. Files such as ANSI-colored logs that mix escape sequences
  with regular text are now classified as text files and linted.
  Files containing only gray-listed bytes remain binary files.
- Bounded memory use when classifying files as text or binary (#22).
  Classification now samples up to 8 KB from the head and 8 KB from the tail
  of each file instead of reading the entire file, following the sampling
  strategy used by zlib (first deflate block) and Google's Magika (head and
  tail chunks). Files smaller than 16 KB are still read fully, so results for
  typical repository files are unchanged. Larger files whose only binary
  bytes sit between the sampled regions are now classified as text.
- Streamed text scanning in fixed 64 KB character chunks instead of iterating
  lines, bounding memory for large files without line breaks, and evaluated
  the character policy once per distinct character per chunk instead of once
  per character. This makes scans of large clean files orders of magnitude
  faster (#22).

## asciilint 0.3.0

### Improvements

- Refactored file discovery logic to load ignore rules before walking the
  filesystem and prune matching directories from `os.walk` (#12).
  Previously, `asciilint` enumerated every file before applying ignore rules,
  which caused noticeable startup lag in projects containing large ignored
  trees such as `.venv/` and `node_modules/`.
  Their contents are now never queried, while configured ignore files,
  negated directory rules, and `--no-gitignore` behavior remain supported.
- Simplified discovery progress to report the files to scan and ignored entries
  without a redundant "Files found" count (#14).

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
