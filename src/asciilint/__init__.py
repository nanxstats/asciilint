"""ASCII and character policy checks for text files."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("asciilint")
except (
    PackageNotFoundError
):  # pragma: no cover - package is not installed in editable docs
    __version__ = "0.0.0"

__all__ = ["__version__"]
