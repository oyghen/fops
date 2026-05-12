__all__ = (
    "create_archive",
    "delete_cache_dirs",
    "delete_cache_files",
    "delete_local_branches",
    "delete_remote_branch_refs",
    "is_git_repo",
    "get_current_branch",
    "rename_extensions",
)

import contextlib
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
    logger.debug("patterns to use: %r", ptrns)

    arch_name = (
        f"{get_timestamp()}-{target_dir.stem}"
        if archive_name is None
        else validate_archive_name(archive_name)
    )
    logger.debug("archive name: %r", arch_name)

    arch_format = validate_archive_format(archive_format)
    logger.debug("archive format: %r", arch_format)

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
            dst = temp_dir / rel_src

            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                dir_count += 1
                logger.info("archived: %s", rel_src)
                continue

            dst.parent.mkdir(parents=True, exist_ok=True)

            if src.is_symlink():
                target_link = os.readlink(src)
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                os.symlink(target_link, dst)
                file_count += 1
                logger.info("archived: %s", rel_src)

            elif src.is_file():
                copy2(src, dst)
                file_count += 1
                logger.info("archived: %s", rel_src)

            else:
                logger.warning("skipping: %s", rel_src)
                continue

        arch = make_archive(str(Path(arch_name)), arch_format, root_dir=str(temp_dir))
        logger.debug("created archive")

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


def is_git_repo(path: Path) -> bool:
    """Return True if path is inside a Git repository."""
    try:
        result = run_command(f"git -C {path} rev-parse --is-inside-work-tree")
        return result == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def delete_cache_dirs(directory_path: Path, cache_dir_patterns: set[str]) -> int:
    """Delete cache directories in the specified directory."""
    count = 0
    for dir_pattern in cache_dir_patterns:
        try:
            for path in directory_path.rglob(dir_pattern):
                if "venv" in str(path):
                    continue
                shutil.rmtree(path.absolute(), ignore_errors=False)
                logger.info("deleted: %s", path.relative_to(directory_path))
                count += 1
        except Exception as exc:
            logger.warning("skipping: dir pattern: %s -> %s", dir_pattern, repr(exc))
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
                logger.info("deleted: %s", path.relative_to(directory_path))
                count += 1
        except Exception as exc:
            logger.warning("skipping: file pattern: %s -> %s", file_pattern, repr(exc))
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
    cur_ext: str,
    new_ext: str,
    make_copy: bool = False,
    recursive: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> int:
    """Rename file extensions in the target directory."""
    logger.info("renaming file extensions in directory: %s", directory_path)

    def normalize(ext: str) -> str:
        return ext if ext.startswith(".") else f".{ext}"

    src_ext = normalize(cur_ext)
    dst_ext = normalize(new_ext)

    lower_src_ext = src_ext.lower()

    count = 0
    paths = directory_path.rglob("*") if recursive else directory_path.iterdir()
    for cur_path in paths:
        rel_path = cur_path.relative_to(directory_path)
        logger.debug("processing: %s", rel_path)

        if not cur_path.is_file():
            logger.debug("skipping: not a file: %s", rel_path)
            continue

        # treat multi-dot extensions (e.g. '.tar.gz') via endswith
        lower_name = cur_path.name.lower()
        matches = (
            lower_name.endswith(lower_src_ext)
            if lower_src_ext.count(".") > 1
            else cur_path.suffix.lower() == lower_src_ext
        )

        if not matches:
            logger.debug("skipping: no match: %s", rel_path)
            continue

        # compute new path
        if lower_src_ext.count(".") > 1 and lower_name.endswith(lower_src_ext):
            # replace trailing multi-dot ext
            new_name = cur_path.name[: -len(src_ext)] + dst_ext
            new_path = cur_path.with_name(new_name)
        else:
            # pathlib.with_suffix accepts '' to remove suffix
            new_path = cur_path.with_suffix(dst_ext)

        rel_new_path = new_path.relative_to(directory_path)
        logger.debug("name of new file: %s", rel_new_path)

        if new_path == cur_path:
            logger.warning("skipping: new name equals current name: %s", rel_new_path)
            continue

        if new_path.exists() and not overwrite:
            logger.warning("skipping: file exists: %s", rel_new_path)
            continue

        if dry_run:
            op = "copy" if make_copy else "rename"
            logger.info("dry-run %s: %s -> %s", op, rel_path, rel_new_path)
            count += 1
            continue

        if make_copy:
            safe_copy(cur_path, new_path)
            logger.info("copied: %s -> %s", rel_path, rel_new_path)
            count += 1
            continue

        if new_path.exists() and overwrite:
            cur_path.replace(new_path)
        else:
            cur_path.rename(new_path)
        logger.info("renamed: %s -> %s", rel_path, rel_new_path)
        count += 1

    return count


def safe_copy(src_file: Path, dst_file: Path) -> None:
    """Safely copy a file with metadata and atomically replace the target if desired."""
    tmp_path: Path | None = None
    try:
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False, dir=dst_file.parent) as temp:
            tmp_path = Path(temp.name)

        copy2(src_file, tmp_path)
        os.replace(str(tmp_path), str(dst_file))

    except Exception:
        with contextlib.suppress(Exception):
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
        raise
