"""Shared input protection for commands that export derived files."""

from os import W_OK, access, readlink, stat_result
from os.path import basename, samestat
from pathlib import Path
from stat import S_IMODE, S_ISDIR, S_ISREG
from tempfile import TemporaryDirectory


def aliases_input(source: Path, output: Path) -> bool:
    try:
        if source.resolve() == output.resolve():
            return True
    except RuntimeError as error:
        raise OSError(f"Cannot check paths {source} and {output}: {error}") from error
    # A failed stat is different from a missing path. In particular, an
    # inaccessible input can still have a writable hard link elsewhere.
    try:
        return samestat(source.stat(), output.stat())
    except (FileNotFoundError, NotADirectoryError):
        return False


def _resolve_destination(path: Path) -> Path:
    try:
        try:
            # Let the filesystem validate traversal first. Some Python versions
            # collapse a non-directory component followed by "..".
            path.stat()
        except FileNotFoundError:
            if not S_ISDIR(path.parent.stat().st_mode):
                raise NotADirectoryError(f"Output parent is a file: {path.parent}")
            if path.is_symlink():
                target = readlink(path)
                # Path would drop a linked target's trailing slash or "/.".
                if basename(target) in ("", ".", ".."):
                    raise FileNotFoundError(f"Output symlink needs a directory: {path}")
                return _resolve_destination(path.parent / target)
            return path.parent.resolve(strict=True) / path.name
        return path.resolve(strict=True)
    except RuntimeError as error:
        # Older Python raises RuntimeError when resolve encounters a symlink loop.
        raise ValueError(f"Cannot resolve output {path}: {error}") from error


class DerivedTextOutput:
    def __init__(self, requested: Path, inputs: tuple[Path, ...]) -> None:
        self.requested = requested.absolute()
        self.destination = _resolve_destination(self.requested)
        self.inputs = inputs
        self._check()

    def _check(self) -> stat_result | None:
        if _resolve_destination(self.requested) != self.destination:
            raise ValueError(f"Output path changed: {self.requested}")
        for source in self.inputs:
            if aliases_input(source, self.destination):
                raise ValueError(
                    f"Output aliases {source}. Choose another output path."
                )
        try:
            existing = self.destination.stat()
        except FileNotFoundError:
            return None
        if not S_ISREG(existing.st_mode):
            raise ValueError(f"Output must be a regular file: {self.requested}")
        if not access(self.destination, W_OK):
            raise PermissionError(f"Output is not writable: {self.requested}")
        return existing

    def write_text(self, data: str) -> None:
        # Write beside the output so a partial write leaves the old file intact.
        with TemporaryDirectory(
            dir=self.destination.parent, prefix=".re-map-export-"
        ) as folder:
            pending = Path(folder) / "output"
            pending.write_text(data)
            # Generation may outlast changes to the requested link or its target.
            existing = self._check()
            if existing is not None:
                pending.chmod(S_IMODE(existing.st_mode))
            pending.replace(self.destination)
