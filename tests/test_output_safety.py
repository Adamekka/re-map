"""Generated files preserve their destination and its permissions."""

import os
import sys
from pathlib import Path
from stat import S_IMODE

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from output_safety import DerivedOutput, aliases_input


@pytest.mark.parametrize("parent_exists", [False, True])
def test_output_cannot_skip_an_invalid_parent(tmp_path, parent_exists):
    existing = tmp_path / "existing.json"
    existing.write_text("previous")
    bad_parent = tmp_path / "not-a-directory"
    if parent_exists:
        bad_parent.touch()
    with pytest.raises(NotADirectoryError if parent_exists else FileNotFoundError):
        DerivedOutput(bad_parent / ".." / existing.name, ())
    assert existing.read_text() == "previous"


def test_output_preserves_the_existing_mode(tmp_path):
    existing = tmp_path / "private.json"
    existing.write_text("previous")
    existing.chmod(0o600)
    DerivedOutput(existing, ()).write_text("updated")
    assert existing.read_text() == "updated"
    assert S_IMODE(existing.stat().st_mode) == 0o600


def test_output_respects_a_read_only_file(tmp_path):
    existing = tmp_path / "read-only.json"
    existing.write_text("previous")
    existing.chmod(0o444)
    if os.access(existing, os.W_OK):
        pytest.skip("The test user can overwrite read-only files")
    with pytest.raises(PermissionError, match="Output is not writable"):
        DerivedOutput(existing, ())
    assert existing.read_text() == "previous"


def test_output_does_not_replace_a_directory_symlink(tmp_path):
    directory = tmp_path / "tracks"
    directory.mkdir()
    link = tmp_path / "link"
    link.symlink_to(directory, target_is_directory=True)
    track = link / "data.bin"
    track.write_bytes(b"disposable track")
    with pytest.raises(ValueError, match="Output must be a regular file"):
        DerivedOutput(link, (track,))
    assert link.is_symlink()
    assert track.read_bytes() == b"disposable track"


@pytest.mark.parametrize("target", ["missing/", "missing/."])
def test_dangling_output_symlink_preserves_directory_requirements(tmp_path, target):
    link = tmp_path / "output.json"
    os.symlink(target, link)
    with pytest.raises(FileNotFoundError):
        DerivedOutput(link, ())
    assert os.readlink(link) == target
    assert not (tmp_path / "missing").exists()


def test_output_symlink_loop_reports_an_input_error(tmp_path):
    link = tmp_path / "loop.json"
    link.symlink_to(link)
    with pytest.raises((OSError, ValueError)):
        DerivedOutput(link, ())
    assert link.is_symlink()


def test_alias_check_reports_older_python_symlink_loop_as_io_error(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    resolve = Path.resolve

    def resolve_with_loop(path, *args, **kwargs):
        if path == source:
            raise RuntimeError("simulated symlink loop")
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_with_loop)
    with pytest.raises(OSError, match="simulated symlink loop"):
        aliases_input(source, output)


def test_output_can_publish_through_a_valid_dangling_symlink(tmp_path):
    link = tmp_path / "output.json"
    target = tmp_path / "new.json"
    link.symlink_to(target)
    DerivedOutput(link, ()).write_text("generated")
    assert link.is_symlink()
    assert target.read_text() == "generated"
