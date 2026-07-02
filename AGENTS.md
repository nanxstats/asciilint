# AGENTS.md

## Project intent

`asciilint` is a small Python CLI for CI-friendly character policy checks.
Keep it minimal, predictable, and easy to run in automation.

## Development workflow

- Use Python 3.11+ features only; configuration is parsed with `tomllib`.
- Use `click` for CLI behavior and user-facing option validation.
- Use `pathspec` for all gitignore syntax matching.
- Preserve the UTF-8-only text processing model: UTF-8 in, UTF-8 out.
- Keep binary detection aligned with the zlib `txtvsbin` algorithm.
- Prefer small dataclasses and pure functions for scanner, policy, config, and output code.
- Tests should use `pytest` and temporary project fixtures instead of mutating repository files.

## Quality loop

Run this before handing off changes:

```bash
uv run isort .
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest
```

## Documentation

The documentation site is under `docs/` and uses Zensical with mkdocs-material
style Markdown organization. Update `zensical.toml` navigation when adding pages.
Keep docs concise and include CLI examples for user-visible behavior changes.
