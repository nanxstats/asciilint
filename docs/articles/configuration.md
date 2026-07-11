# Configuration

`asciilint` looks for `asciilint.toml` in the current directory and then upward.
Use `--config` to choose a file explicitly or `--no-config` to disable config
loading.

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

## Ignore files

`.gitignore` is respected by default. Additional ignore files can be configured
in TOML or passed on the command line:

```bash
asciilint . --ignore-file .asciilintignore --ignore-file tools/asciilint.ignore
```

Every ignore file must use gitignore syntax. Matching is handled by `pathspec`.

Directory entries are matched before `asciilint` descends into them, so the
contents of ignored trees such as `.venv/` and `node_modules/` are never
enumerated.

Negated directory patterns are applied before that decision, so a
rule such as `!generated/keep/` can keep a matching subtree in the scan.

The discovery summary's "Files to scan" value counts files after ignore
filtering. Each pruned directory contributes one ignored entry. It does not
count files under that directory because they are intentionally never queried.

## Character policy

The default policy is ASCII-only:

```toml
allowed_ranges = ["U+0000-U+007F"]
```

Ranges support these forms:

- `U+0000-U+007F`
- `0x20..0x7e`
- `32-126`
- `a-z`
- `U+00A9` for a single code point

Allow rules define the full permitted set. Deny rules are then applied on top
and take precedence.

Allow Latin-1 but reject `é`:

```toml
[asciilint]
allowed_ranges = ["U+0000-U+00FF"]
disallowed_chars = ["é"]
```

Allow any Unicode character except selected punctuation:

```bash
asciilint . --allow-any --disallowed-char "&rarr;" --disallowed-range U+2000-U+206F
```

## UTF-8 only

The processing model is UTF-8 in, UTF-8 out. Convert text files to UTF-8 before
running `asciilint`. If a file looks like text but cannot be decoded as UTF-8,
`asciilint` reports a read error and skips that file.
