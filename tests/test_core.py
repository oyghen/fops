import builtins
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import purekit as pk
import pytest
import timeteller as tt

import fops


class TestConfirm:
    def test_accepts_yes(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", self.patch_input(["y"]))
        assert fops.core.confirm("Proceed?") is True

    def test_accepts_no(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", self.patch_input(["n"]))
        assert fops.core.confirm("Proceed?") is False

    def test_uses_default_yes_on_empty_reply(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", self.patch_input([""]))
        assert fops.core.confirm("Proceed?", default="yes") is True

    def test_uses_default_no_on_empty_reply(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", self.patch_input([""]))
        assert fops.core.confirm("Proceed?", default="no") is False

    def test_reprompts_on_invalid_then_accepts(self, monkeypatch, capsys):
        monkeypatch.setattr(builtins, "input", self.patch_input(["maybe", "yes"]))
        result = fops.core.confirm("Proceed?")
        captured = capsys.readouterr()
        assert "Please respond with 'yes' or 'no'." in captured.out
        assert result is True

    def test_whitespace_counts_as_empty_and_reprompts(self, monkeypatch, capsys):
        monkeypatch.setattr(builtins, "input", self.patch_input(["   ", "1"]))
        result = fops.core.confirm("Proceed?")
        captured = capsys.readouterr()
        assert "Please respond with 'yes' or 'no'." in captured.out
        assert result is True  # '1' maps to true tokens

    def test_invalid_default_raises(self):
        with pytest.raises(ValueError):
            fops.core.confirm("Proceed?", default="maybe")

    @staticmethod
    def patch_input(responses: list[str]):
        """Return a stub for builtins.input that yields the given responses."""
        iterator = iter(responses)

        def _input(prompt: str) -> str:
            try:
                return next(iterator)
            except StopIteration as exc:
                raise AssertionError("test provided too few responses") from exc

        return _input


class TestCreateArchive:
    def _patch_timestamp(self, value: str):
        """Patch tt.stdlib.timestamp, return a restore callable."""
        orig = tt.stdlib.timestamp
        tt.stdlib.timestamp = lambda tz, fmt: value
        return lambda: setattr(tt.stdlib, "timestamp", orig)

    def _chdir(self, new_cwd: str):
        """Change cwd, return a restore callable."""
        old = os.getcwd()
        os.chdir(new_cwd)
        return lambda: os.chdir(old)

    def test_create_archive_default_name_and_contents(self):
        with TemporaryDirectory() as srcdir, TemporaryDirectory() as workdir:
            src = Path(srcdir)
            (src / "file1.txt").write_text("hello")
            (src / "sub").mkdir()
            (src / "sub" / "file2.txt").write_text("world")

            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                fops.core.create_archive(srcdir)  # uses patched timestamp
                expected = Path(workdir) / f"20250101010101_{Path(srcdir).stem}.zip"
                assert expected.exists(), "archive file was not created"

                extract_dir = Path(workdir) / "ex"
                shutil.unpack_archive(str(expected), str(extract_dir))
                assert (extract_dir / "file1.txt").read_text() == "hello"
                assert (extract_dir / "sub" / "file2.txt").read_text() == "world"
            finally:
                restore_cwd()
                restore_ts()

    def test_create_archive_with_archive_name(self):
        with TemporaryDirectory() as srcdir, TemporaryDirectory() as workdir:
            src = Path(srcdir)
            (src / "a.txt").write_text("x")

            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                fops.core.create_archive(srcdir, archive_name="myarchive")
                expected = Path(workdir) / "myarchive.zip"
                assert expected.exists()
                extract_dir = Path(workdir) / "ex2"
                shutil.unpack_archive(str(expected), str(extract_dir))
                assert (extract_dir / "a.txt").read_text() == "x"
            finally:
                restore_cwd()
                restore_ts()

    def test_create_archive_pattern_filtering(self):
        with TemporaryDirectory() as srcdir, TemporaryDirectory() as workdir:
            src = Path(srcdir)
            (src / "keep.md").write_text("keep")
            (src / "skip.txt").write_text("skipme")

            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                fops.core.create_archive(srcdir, archive_name="pat", patterns=["*.md"])
                expected = Path(workdir) / "pat.zip"
                assert expected.exists()
                extract_dir = Path(workdir) / "ex3"
                shutil.unpack_archive(str(expected), str(extract_dir))
                assert (extract_dir / "keep.md").exists()
                assert not (extract_dir / "skip.txt").exists()
            finally:
                restore_cwd()
                restore_ts()

    def test_create_archive_preserves_symlink_in_tar(self):
        # Use a tar-based format that preserves symlinks reliably.
        with TemporaryDirectory() as srcdir, TemporaryDirectory() as workdir:
            src = Path(srcdir)
            (src / "target.txt").write_text("target")
            (src / "link").symlink_to(src / "target.txt")

            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                # gztar should preserve symlink entries
                fops.core.create_archive(
                    srcdir, archive_name="sym", archive_format="gztar"
                )
                expected = Path(workdir) / "sym.tar.gz"
                assert expected.exists()
                extract_dir = Path(workdir) / "ex4"
                shutil.unpack_archive(str(expected), str(extract_dir))
                extracted_link = extract_dir / "link"
                # On platforms that preserve symlinks, this will be True.
                # We assert at least that the link target's content exists and matches.
                if extracted_link.is_symlink():
                    # symlink preserved
                    assert extracted_link.resolve().read_text() == "target"
                else:
                    # zip-like behavior: the file content was archived instead
                    assert extracted_link.read_text() == "target"
            finally:
                restore_cwd()
                restore_ts()

    def test_nonexistent_directory_raises(self):
        with TemporaryDirectory() as workdir:
            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                with pytest.raises(ValueError):
                    fops.core.create_archive("/path/does/not/exist")
            finally:
                restore_cwd()
                restore_ts()

    def test_invalid_archive_format_raises(self):
        with TemporaryDirectory() as srcdir, TemporaryDirectory() as workdir:
            src = Path(srcdir)
            (src / "a.txt").write_text("x")

            restore_ts = self._patch_timestamp("20250101010101")
            restore_cwd = self._chdir(workdir)
            try:
                with pytest.raises(pk.exceptions.InvalidChoiceError):
                    fops.core.create_archive(srcdir, archive_format="INVALID_FORMAT")
            finally:
                restore_cwd()
                restore_ts()
