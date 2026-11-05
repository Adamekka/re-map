"""Shared input protection for commands that export derived files."""

from pathlib import Path


def aliases_input(source: Path, output: Path) -> bool:
    # Resolving catches path and symbolic aliases; samefile also catches hard links.
    return source.resolve() == output.resolve() or (
        output.exists() and output.samefile(source)
    )
