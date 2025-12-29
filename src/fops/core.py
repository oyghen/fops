__all__ = ("clear_cache", "confirm")

import logging
import shutil
from os import PathLike
from pathlib import Path

logger = logging.getLogger(__name__)


def clear_cache(directory_path: str | Path | PathLike[str]) -> None:
    root = Path(directory_path).resolve()
    directories = [
        "__pycache__",
        ".pytest_cache",
        ".ipynb_checkpoints",
        ".ruff_cache",
        "spark-warehouse",
    ]
    file_extensions = [
        "*.py[co]",
        ".coverage",
        ".coverage.*",
    ]

    for directory in directories:
        for path in root.rglob(directory):
            if "venv" in str(path):
                continue
            shutil.rmtree(path.absolute(), ignore_errors=False)
            logger.info("deleted - %s", path)

    for file_extension in file_extensions:
        for path in root.rglob(file_extension):
            if "venv" in str(path):
                continue
            path.unlink()
            logger.info("deleted - %s", path)


def confirm(prompt: str, default: str | None = None) -> bool:
    """Return True if the user confirms ('yes'); repeats until valid input."""
    if default not in (None, "yes", "no"):
        raise ValueError(f"invalid {default=!r}; expected None, 'yes', or 'no'")

    true_tokens = frozenset(("y", "yes", "t", "true", "on", "1"))
    false_tokens = frozenset(("n", "no", "f", "false", "off", "0"))
    prompt_map = {None: "[y/n]", "yes": "[Y/n]", "no": "[y/N]"}
    suffix = prompt_map[default]

    while True:
        reply = input(f"{prompt} {suffix} ").strip().lower()

        if not reply:
            if default is not None:
                return default == "yes"
            print("Please respond with 'yes' or 'no'.")
            continue

        if reply in true_tokens:
            return True
        if reply in false_tokens:
            return False

        print("Please respond with 'yes' or 'no'.")
