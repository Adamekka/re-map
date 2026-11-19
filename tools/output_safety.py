"""Shared input protection for commands that export derived files."""

from os.path import samestat
from pathlib import Path


def aliases_input(source: Path, output: Path) -> bool:
    if source.resolve() == output.resolve():
        return True
    # A failed stat is different from a missing path. In particular, an
    # inaccessible input can still have a writable hard link elsewhere.
    try:
        return samestat(source.stat(), output.stat())
    except (FileNotFoundError, NotADirectoryError):
        return False
