__all__ = (
    "CACHE_DIRECTORIES",
    "CACHE_FILE_EXTENSIONS",
    "clear_cache",
    "confirm",
    "create_archive",
    "iter_lines",
    "terminal_width",
)

import logging
import os
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from os import PathLike
from pathlib import Path
from shutil import copy2, get_archive_formats, get_terminal_size, make_archive
from typing import Final

from fops import utils

logger = logging.getLogger(__name__)


CACHE_DIRECTORIES: Final[tuple[str, ...]] = (
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
    ".ruff_cache",
    "spark-warehouse",
)

CACHE_FILE_EXTENSIONS: Final[tuple[str, ...]] = (
    "*.py[co]",
    ".coverage",
    ".coverage.*",
)


def clear_cache(
    directory_path: str | Path | PathLike[str],
    cache_directories: Sequence[str] | None = None,
    cache_file_extensions: Sequence[str] | None = None,
) -> None:
    root = Path(directory_path).resolve()

    if cache_directories is None:
        cache_directories = CACHE_DIRECTORIES

    if cache_file_extensions is None:
        cache_file_extensions = CACHE_FILE_EXTENSIONS

    for directory in cache_directories:
        for path in root.rglob(directory):
            if "venv" in str(path):
                continue
            shutil.rmtree(path.absolute(), ignore_errors=False)
            logger.info("deleted - %s", path)

    for file_extension in cache_file_extensions:
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


def create_archive(
    directory_path: str | Path | PathLike[str],
    archive_name: str | None = None,
    patterns: Sequence[str] | None = None,
    archive_format: str = "zip",
) -> Path:
    """Return the path of the created archive file."""
    dir_path = Path(directory_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError(f"{directory_path!r} does not exist or is not a directory")

    patterns = list(patterns) if patterns else ["**/*"]
    archive_format = archive_format.lower()
    supported = {fmt for fmt, _ in get_archive_formats()}
    if archive_format not in supported:
        raise ValueError(
            f"invalid choice {archive_format!r}; expected a value from {supported!r}"
        )

    if archive_name is None:
        base_name = f"{utils.utctimestamp()}_{dir_path.stem}"
    else:
        if Path(archive_name).name != archive_name:
            raise ValueError("archive_name must not contain directory components")
        base_name = archive_name

    # collect matches deterministically and deduplicate
    matched: set[Path] = set()
    for pattern in patterns:
        matched.update(dir_path.rglob(pattern))

    # sort by relative path for deterministic archive contents/order
    paths = sorted((p for p in matched), key=lambda p: str(p.relative_to(dir_path)))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        for src_path in paths:
            logger.debug("processing - %s", src_path)
            try:
                rel = src_path.relative_to(dir_path)
            except Exception:
                # skip anything not under target (shouldn't happen with rglob)
                continue

            dst_path = tmpdir_path / rel
            if src_path.is_dir():
                dst_path.mkdir(parents=True, exist_ok=True)
                continue

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_symlink():
                target_link = os.readlink(src_path)
                if dst_path.exists() or dst_path.is_symlink():
                    dst_path.unlink()
                os.symlink(target_link, dst_path)

            elif src_path.is_file():
                copy2(src_path, dst_path)

            else:
                continue

        archive_path = make_archive(
            str(Path(base_name)),
            archive_format,
            root_dir=str(tmpdir_path),
        )

    return Path(archive_path)


def iter_lines(
    filepath: str | Path | PathLike[str],
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
) -> Iterator[str]:
    """Return an iterator over text lines from filepath."""
    path = os.fspath(filepath)
    with open(path, encoding=encoding, errors=errors, newline=newline) as fh:
        yield from fh


def terminal_width(default: int = 79) -> int:
    """Return the current terminal width or a fallback value."""
    try:
        return get_terminal_size().columns
    except OSError:
        return default
