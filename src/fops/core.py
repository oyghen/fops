__all__ = (
    "PathLikeStr",
    "PROTECTED_BRANCHES",
    "CACHE_DIRECTORIES",
    "CACHE_FILE_EXTENSIONS",
    "delete_cache",
    "confirm",
    "create_archive",
    "iter_lines",
    "terminal_width",
    "delete_local_branches",
    "delete_remote_branch_refs",
    "get_current_branch_name",
    "get_local_branch_names",
    "get_remote_branch_names",
    "get_last_commit_hash",
    "run_command",
    "get_installed_package_count",
    "rename_extensions",
    "safe_copy",
)

import contextlib
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from importlib import metadata
from pathlib import Path
from shutil import copy2, get_archive_formats, get_terminal_size, make_archive
from typing import Final, TypeAlias

from fops import utils

PathLikeStr: TypeAlias = str | Path | os.PathLike[str]

logger = logging.getLogger(__name__)

PROTECTED_BRANCHES: Final[frozenset[str]] = frozenset({"main", "master", "develop"})

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


def delete_cache(
    directory_path: PathLikeStr,
    cache_directories: Sequence[str] | None = None,
    cache_file_extensions: Sequence[str] | None = None,
) -> None:
    """Delete cache directories and files in the specified directory."""
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
    logger.info("done with deleting cache directories")

    for file_extension in cache_file_extensions:
        for path in root.rglob(file_extension):
            if "venv" in str(path):
                continue
            path.unlink()
            logger.info("deleted - %s", path)
    logger.info("done with deleting cache files")


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
    directory_path: PathLikeStr,
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
    filepath: PathLikeStr,
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


def delete_local_branches() -> None:
    """Delete local git branches except protected ones."""
    logger.debug("running '%s'", utils.get_caller_name())
    current = get_current_branch_name()
    exclude = PROTECTED_BRANCHES | {current}

    local = get_local_branch_names()
    to_delete = [b for b in local if b not in exclude]

    if not to_delete:
        logger.info("no local branches to delete")
        return

    logger.debug("deleting %d local branch(es): %s", len(to_delete), to_delete)
    for branch in to_delete:
        try:
            run_command(f"git branch -D {branch}", label=utils.get_caller_name())
            logger.info("deleted local branch '%s'", branch)
        except subprocess.CalledProcessError as exc:
            logger.exception(
                "failed deleting local branch %s; exit=%s; stderr=%s",
                branch,
                getattr(exc, "returncode", None),
                getattr(exc, "stderr", None),
            )


def delete_remote_branch_refs() -> None:
    """Delete remote-tracking git branch refs except protected ones."""
    logger.debug("running '%s'", utils.get_caller_name())
    current = get_current_branch_name()
    exclude = PROTECTED_BRANCHES | {current}

    remote = get_remote_branch_names()
    to_delete = [r for r in remote if r.split("/", 1)[-1] not in exclude]

    if not to_delete:
        logger.info("no remote-tracking refs to delete")
        return

    logger.debug("deleting %d remote ref(s): %s", len(to_delete), to_delete)
    for ref in to_delete:
        try:
            run_command(f"git branch -r -d {ref}", label=utils.get_caller_name())
            logger.info("deleted remote ref '%s'", ref)
        except subprocess.CalledProcessError as exc:
            logger.exception(
                "failed deleting remote ref %s; exit=%s; stderr=%s",
                ref,
                getattr(exc, "returncode", None),
                getattr(exc, "stderr", None),
            )


def get_current_branch_name() -> str:
    """Return current branch name as string."""
    return run_command("git rev-parse --abbrev-ref HEAD", label=utils.get_caller_name())


def get_local_branch_names() -> list[str]:
    """Return list of local branch names."""
    out = run_command("git branch", label=utils.get_caller_name())
    branches: list[str] = []
    for line in out.splitlines():
        branches.append(line.lstrip("*").strip())
    return branches


def get_remote_branch_names() -> list[str]:
    """Return list of remote-tracking branch refs."""
    out = run_command("git branch --remotes", label=utils.get_caller_name())
    branches: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if "->" in line:
            continue
        branches.append(line)
    return branches


def get_last_commit_hash(max_length: int | None = None) -> str:
    """Return the full or truncated commit hash of the current branch."""
    if max_length is not None:
        if not isinstance(max_length, int):
            raise TypeError(
                f"unsupported type {type(max_length).__name__!r}; expected int or None"
            )
        if max_length < 1:
            raise ValueError(f"invalid value {max_length!r}; expected >= 1")

    commit = run_command("git rev-parse HEAD", label=utils.get_caller_name())
    if not commit:
        raise RuntimeError("git returned an empty commit hash")

    return commit if max_length is None else commit[:max_length]


def run_command(command: str | Sequence[str], label: str) -> str:
    """Return stdout as string of the executed command."""
    cmd = shlex.split(command) if isinstance(command, str) else list(command)
    response = subprocess.run(cmd, capture_output=True, text=True, check=True)
    logger.debug("'%s' ran '%s'", label, " ".join(cmd))
    return response.stdout.strip()


def get_installed_package_count() -> int:
    """Return the number of installed packages for the current Python environment."""
    try:
        count = sum(1 for _ in metadata.distributions())
    except Exception:
        count = 0

    # fallback: use the same interpreter's pip to get a reliable package list
    if count < 10:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=freeze"],
                check=True,
                capture_output=True,
                text=True,
            )
            # ignore blank lines and count non-empty entries
            lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
            return len(lines)
        except (subprocess.SubprocessError, OSError):
            # if pip fails, return what metadata provided (possibly 0)
            return int(count)

    return int(count)


def rename_extensions(
    directory_path: PathLikeStr,
    old_ext: str | None,
    new_ext: str,
    *,
    create_copy: bool = False,
    recursive: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    """Rename (or copy) files in a directory by changing their extensions."""
    logger.debug(
        "running '%s' with %s",
        utils.get_caller_name(),
        {
            "directory_path": directory_path,
            "old_ext": old_ext,
            "new_ext": new_ext,
            "create_copy": create_copy,
            "recursive": recursive,
            "overwrite": overwrite,
            "dry_run": dry_run,
        },
    )

    dir_path = Path(directory_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError(f"{directory_path!r} does not exist or is not a directory")

    def _normalize(ext: str | None) -> str | None:
        if ext is None:
            return None
        if ext == "":
            return ""
        return ext if ext.startswith(".") else f".{ext}"

    src_ext = _normalize(old_ext)
    dst_ext = _normalize(new_ext)
    if dst_ext is None:
        raise ValueError("new_ext must be provided")

    # iterable of Path objects
    file_paths = dir_path.rglob("*") if recursive else dir_path.iterdir()

    for file_path in file_paths:
        logger.debug("processing: %s", file_path)

        if not file_path.is_file():
            logger.debug("skipping - not a file: %s", file_path)
            continue

        name = file_path.name
        lower_name = name.lower()

        # decide if file matches src_ext
        if src_ext is None:
            matches = True
        else:
            src_lower = src_ext.lower()
            # treat multi-dot extensions (e.g. '.tar.gz') via endswith
            if src_lower.count(".") > 1:
                matches = lower_name.endswith(src_lower)
            else:
                matches = file_path.suffix.lower() == src_lower

        if not matches:
            logger.debug("skipping - not a match: %s", file_path)
            continue

        # compute new path
        if (
            src_ext
            and src_ext.lower().count(".") > 1
            and lower_name.endswith(src_ext.lower())
        ):
            # replace trailing multi-dot ext
            new_name = name[: -len(src_ext)] + dst_ext
            new_path = file_path.with_name(new_name)
        else:
            # pathlib.with_suffix accepts '' to remove suffix
            new_path = file_path.with_suffix(dst_ext)

        # no-op
        if new_path == file_path:
            logger.debug("skipping - new_path is current file_path")
            continue

        if new_path.exists() and not overwrite:
            raise FileExistsError(f"file already exists: {new_path}")

        if dry_run:
            op = "copy" if create_copy else "rename"
            logger.info("[dry-run] %s %s -> %s", op, file_path, new_path)
            continue

        if create_copy:
            safe_copy(file_path, new_path, overwrite=overwrite)
            logger.info("copied %s -> %s", file_path, new_path)
        else:
            # use replace when allowing overwrite (atomic where supported)
            if overwrite and new_path.exists():
                file_path.replace(new_path)
            else:
                file_path.rename(new_path)
            logger.info("renamed %s -> %s", file_path, new_path)


def safe_copy(
    old_file: PathLikeStr,
    new_file: PathLikeStr,
    *,
    overwrite: bool = False,
) -> None:
    """Safely copy a file with metadata and atomically replace the target if desired."""
    src = Path(old_file)
    dst = Path(new_file)

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"source does not exist or is not a file: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and not overwrite:
        raise FileExistsError(f"target already exists: {dst}")

    tmp_path: Path | None = None
    try:
        # create a named temporary file in the destination directory for atomic replace
        with tempfile.NamedTemporaryFile(delete=False, dir=dst.parent) as tmp:
            tmp_path = Path(tmp.name)
        copy2(src, tmp_path)  # copy2 preserves metadata (mtime, permissions, flags)
        os.replace(str(tmp_path), str(dst))  # atomic rename (replace) to final dst
    except Exception:
        # best-effort cleanup of temp file
        with contextlib.suppress(Exception):
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
        raise
