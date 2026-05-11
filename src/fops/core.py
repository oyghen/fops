__all__ = (
    "create_archive",
    "delete_cache_dirs",
    "delete_cache_files",
    "delete_local_branches",
    "delete_remote_branch_refs",
    "rename_extensions",
)

import contextlib
import inspect
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from shutil import copy2, get_archive_formats, make_archive
from typing import TypeVar

import timeteller as tt
from clsforge import InvalidChoiceError

T = TypeVar("T")


logger = logging.getLogger(__name__)


def create_archive(
    directory_path: Path,
    patterns: Sequence[str] | None = None,
    archive_name: str | None = None,
    archive_format: str = "zip",
) -> Path:
    """Return path of the created archive relative to the current working directory."""
    target_dir = directory_path
    ptrns = ["**/*"] if patterns is None else tuple(patterns)
    arch_name = (
        f"{get_timestamp()}-{target_dir.stem}"
        if archive_name is None
        else validate_archive_name(archive_name)
    )
    arch_format = validate_archive_format(archive_format)

    # collect matches deterministically and deduplicate
    matched_paths: set[Path] = set()
    for ptrn in ptrns:
        matched_paths.update(target_dir.rglob(ptrn))

    # sort by relative path for deterministic archive contents/order
    paths = sorted(matched_paths, key=lambda p: str(p.relative_to(target_dir)))

    dir_count = 0
    file_count = 0
    logger.info("archiving %d path(s) in directory: %s", len(paths), target_dir)
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        for src in paths:
            rel_src = src.relative_to(target_dir)
            logger.debug("processing: %s", rel_src)
            dst = temp_dir / rel_src

            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                dir_count += 1
                continue

            dst.parent.mkdir(parents=True, exist_ok=True)

            if src.is_symlink():
                target_link = os.readlink(src)
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                os.symlink(target_link, dst)
                file_count += 1

            elif src.is_file():
                copy2(src, dst)
                file_count += 1

            else:
                continue

        arch = make_archive(str(Path(arch_name)), arch_format, root_dir=str(temp_dir))

    logger.info("number of archived directories: %s", dir_count)
    logger.info("number of archived files: %s", file_count)

    return Path(arch).relative_to(Path.cwd())


def get_timestamp() -> str:
    """Return a timestamp string."""
    return tt.core.utc_timestamp_ms().translate(str.maketrans({":": "-", ".": "-"}))


def validate_archive_name(archive_name: str) -> str:
    """Return validated archive name."""
    if Path(archive_name).name != archive_name:
        raise ValueError("archive_name must not contain directory components")
    return archive_name


def validate_archive_format(archive_format: str) -> str:
    """Return validated archive format."""
    fmt_choice = archive_format.lower()
    fmt_choices = {fmt for fmt, _ in get_archive_formats()}
    if fmt_choice not in fmt_choices:
        raise InvalidChoiceError(fmt_choice, fmt_choices)
    return fmt_choice


def delete_cache_dirs(directory_path: Path, cache_dir_patterns: set[str]) -> int:
    """Delete cache directories in the specified directory."""
    count = 0
    for dir_pattern in cache_dir_patterns:
        try:
            for path in directory_path.rglob(dir_pattern):
                if "venv" in str(path):
                    continue
                shutil.rmtree(path.absolute(), ignore_errors=False)
                logger.debug("deleted: %s", path.relative_to(directory_path))
                count += 1
        except Exception as exc:
            logger.warning("skipping dir pattern: %s -> %s", dir_pattern, repr(exc))
            continue
    return count


def delete_cache_files(directory_path: Path, cache_file_patterns: set[str]) -> int:
    """Delete cache files in the specified directory."""
    count = 0
    for file_pattern in cache_file_patterns:
        try:
            for path in directory_path.rglob(file_pattern):
                if "venv" in str(path):
                    continue
                path.unlink()
                logger.debug("deleted: %s", path.relative_to(directory_path))
                count += 1
        except Exception as exc:
            logger.warning("skipping file pattern: %s -> %s", file_pattern, repr(exc))
            continue
    return count


def delete_local_branches(protected_branches: set[str]) -> int:
    """Delete local git branches except protected ones."""
    local = get_local_branch_names()
    to_delete = [b for b in local if b not in protected_branches]
    if not to_delete:
        logger.info("no local branches to delete")
        return 0

    logger.debug("local branches to delete: %d", len(to_delete))
    for branch in to_delete:
        try:
            run_command(f"git branch -D {branch}")
            logger.info("deleted: %s", branch)
        except subprocess.CalledProcessError as exc:
            logger.exception("error deleting local branch: %s", branch)
            raise exc

    return len(to_delete)


def delete_remote_branch_refs(protected_branches: set[str]) -> int:
    """Delete remote-tracking git branch refs except protected ones."""
    remote = get_remote_branch_names()
    to_delete = [r for r in remote if r.split("/", 1)[-1] not in protected_branches]
    if not to_delete:
        logger.info("no remote-tracking refs to delete")
        return 0

    logger.debug("remote refs to delete: %d", len(to_delete))
    for ref in to_delete:
        try:
            run_command(f"git branch -r -d {ref}")
            logger.info("deleted: %s", ref)
        except subprocess.CalledProcessError as exc:
            logger.exception("error deleting remote ref: %s", ref)
            raise exc

    return len(to_delete)


def get_current_branch() -> str:
    """Return the current branch name."""
    return run_command("git rev-parse --abbrev-ref HEAD")


def get_local_branch_names() -> list[str]:
    """Return list of local branch names."""
    out = run_command("git branch")
    branches: list[str] = []
    for line in out.splitlines():
        branches.append(line.lstrip("*").strip())
    return branches


def get_remote_branch_names() -> list[str]:
    """Return list of remote-tracking branch refs."""
    out = run_command("git branch --remotes")
    branches: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if "->" in line:
            continue
        branches.append(line)
    return branches


def run_command(command: str | Sequence[str]) -> str:
    """Return stdout as string of the executed command."""
    cmd = shlex.split(command) if isinstance(command, str) else list(command)
    response = subprocess.run(cmd, capture_output=True, text=True, check=True)
    logger.debug("run cmd: %s", " ".join(cmd))
    return response.stdout.strip()


def rename_extensions(
    directory_path: Path,
    old_ext: str | None,
    new_ext: str,
    create_copy: bool = False,
    recursive: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    """Rename (or copy) files in a directory by changing their extensions."""
    logger.info("processing directory: %s", directory_path)
    logger.debug(
        "running '%s' with %s",
        get_caller_name(),
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
    file_paths = directory_path.rglob("*") if recursive else directory_path.iterdir()

    for file_path in file_paths:
        rel_file_path = file_path.relative_to(directory_path)
        logger.debug("processing: %s", rel_file_path)

        if not file_path.is_file():
            logger.debug("skipping: not a file: %s", rel_file_path)
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
            logger.debug("skipping: not a match: %s", rel_file_path)
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
            logger.debug("skipping: new_path is current file_path")
            continue

        rel_new_path = new_path.relative_to(directory_path)

        if new_path.exists() and not overwrite:
            raise FileExistsError(f"file already exists: {rel_new_path}")

        if dry_run:
            op = "copy" if create_copy else "rename"
            logger.info("[dry-run] %s %s -> %s", op, rel_file_path, rel_new_path)
            continue

        if create_copy:
            safe_copy(file_path, new_path, directory_path, overwrite=overwrite)
            logger.info("copied %s -> %s", rel_file_path, rel_new_path)
        else:
            # use replace when allowing overwrite (atomic where supported)
            if overwrite and new_path.exists():
                file_path.replace(new_path)
            else:
                file_path.rename(new_path)
            logger.info("renamed %s -> %s", rel_file_path, rel_new_path)


def safe_copy(
    old_file: Path, new_file: Path, dir_path: Path, *, overwrite: bool = False
) -> None:
    """Safely copy a file with metadata and atomically replace the target if desired."""
    src = Path(old_file)
    dst = Path(new_file)
    rel_src = src.relative_to(dir_path)
    rel_dst = dst.relative_to(dir_path)

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"source does not exist or is not a file: {rel_src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and not overwrite:
        raise FileExistsError(f"target already exists: {rel_dst}")

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


def get_caller_name(depth: int = 1) -> str:
    """Return the name of the calling function; depth=1 is the immediate caller."""
    if depth < 1:
        raise ValueError(f"invalid {depth=!r}; expected >= 1")

    frame = inspect.currentframe()
    try:
        caller = frame
        for _ in range(depth):
            caller = caller.f_back if caller is not None else None
        if caller is None:
            raise RuntimeError("expected to be executed within a function")
        return caller.f_code.co_name
    finally:
        del frame
