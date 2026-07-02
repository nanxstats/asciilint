# Get started

Install `asciilint` with pip:

```bash
pip install asciilint
```

Or add it to a project managed by `uv`:

```bash
uv add --dev asciilint
```

Run it from the project root:

```bash
asciilint .
```

A passing run is intentionally quiet:

```text
> Checking characters in /path/to/project
Files found: 8, 7 to scan, 1 ignored
Checking text:
✓✓✓✓✓✓
Files checked: 6 text, 1 binary skipped, 0 read error(s)
No issues :-)
```

Status characters are written while files are scanned, and long status lines are
wrapped so CI logs keep receiving progress.

A failing run points to the file, line, column, code point, and reason:

```text
Issues :-(
> Disallowed characters
  1. README.md
     1. [L004:C011] U+00E9 "\xe9" not allowed by policy
Summary: 1 disallowed character(s), 0 read error(s)
```

Use it in CI as a normal command. The process exits with `1` when it finds a
policy violation or a UTF-8 read error.
