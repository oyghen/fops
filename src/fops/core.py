__all__ = ("clear_cache",)

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
