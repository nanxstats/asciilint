# asciilint

[![PyPI version](https://img.shields.io/pypi/v/asciilint)](https://pypi.org/project/asciilint/)
![Python versions](https://img.shields.io/pypi/pyversions/asciilint)
[![CI tests](https://github.com/nanxstats/asciilint/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/nanxstats/asciilint/actions/workflows/ci-tests.yml)
[![Mypy check](https://github.com/nanxstats/asciilint/actions/workflows/mypy.yml/badge.svg)](https://github.com/nanxstats/asciilint/actions/workflows/mypy.yml)
[![Ruff check](https://github.com/nanxstats/asciilint/actions/workflows/ruff-check.yml/badge.svg)](https://github.com/nanxstats/asciilint/actions/workflows/ruff-check.yml)
[![Documentation](https://github.com/nanxstats/asciilint/actions/workflows/docs.yml/badge.svg)](https://nanx.me/asciilint/)
![License](https://img.shields.io/pypi/l/asciilint)

Minimal, configurable, CI-friendly character policy checks for text files.

By default, `asciilint` recursively scans a project and fails when UTF-8
text files contain non-ASCII characters. It can also enforce arbitrary Unicode
allowlists and denylists, so it is useful for broader character policy checks.

## Installation

```bash
pip install asciilint
```

With `uv`:

```bash
uv add asciilint
```

## Usage

```bash
asciilint .
```

Example failing output:

```text
> Checking characters in /path/to/project
Files found: 3, 2 text, 0 binary skipped, 1 ignored
Checking text: ✓x

Issues :-(
> Disallowed characters
  1. docs/page.md
     1. [L012:C018] U+2014 "\u2014" not allowed by policy
Summary: 1 disallowed character(s), 0 read error(s)
```

Exit code `0` means no issues. Exit code `1` means disallowed characters or
read errors were found.

## Configuration

Create `asciilint.toml`:

```toml
[asciilint]
paths = ["."]
respect_gitignore = true
ignore_files = [".asciilintignore"]
allowed_ranges = ["U+0000-U+007F"]
allowed_chars = []
disallowed_ranges = []
disallowed_chars = []
max_issues_per_file = 5
```

Ignore files use gitignore syntax and are matched with `pathspec`.
`.gitignore` is respected by default.
You can add other ignore files, for example:

```bash
asciilint . --ignore-file .asciilintignore --ignore-file config/lint.ignore
```

Character ranges can be written as `U+0000-U+007F`, `0x20..0x7e`, `32-126`, or
single code points such as `U+00A9`. Deny rules take precedence over allow rules.

To allow any Unicode character except a small denylist:

```bash
asciilint . --allow-any --disallowed-char "→" --disallowed-range U+2000-U+206F
```

## UTF-8 and binary files

`asciilint` assumes text files are UTF-8. Files that are classified as text but
cannot be decoded as UTF-8 are reported explicitly and skipped. Binary files are
skipped automatically using the zlib `txtvsbin` heuristic.
