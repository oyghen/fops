import builtins

import pytest

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
