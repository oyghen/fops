import functools
import logging
import sys
from enum import IntEnum
from pathlib import Path
from typing import Annotated, Final

import typer

import fops
from fops import core

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False)

create = typer.Typer(help="Create commands.")
delete = typer.Typer(help="Delete commands.")
rename = typer.Typer(help="Rename commands.")

app.add_typer(create, name="create")
app.add_typer(delete, name="delete")
app.add_typer(rename, name="rename")


PROTECTED_BRANCHES: Final[set[str]] = {"main", "master", "develop"}

CACHE_DIR_PATTERNS: Final[set[str]] = {
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
    ".ruff_cache",
    "spark-warehouse",
}


CACHE_FILE_PATTERNS: Final[set[str]] = {
    "*.py[co]",
    ".coverage",
    ".coverage.*",
}


class ExitCode(IntEnum):
    SUCCESS = 0
    ERROR = 1


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[36m",  # cyan
        logging.INFO: "\x1b[32m",  # green
        logging.WARNING: "\x1b[33m",  # yellow
        logging.ERROR: "\x1b[31m",  # red
        logging.CRITICAL: "\x1b[1;31m",  # bold red
    }

    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname:<8s}{self.RESET}"
        return super().format(record)


def setup_logging(level: int) -> None:
    """Set up application logging configuration."""
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    fmt = "[ %(levelname)-8s ] %(message)s"
    handler.setFormatter(ColorFormatter(fmt))

    root.addHandler(handler)
    root.setLevel(level)


def validate_directory_path(directory_path: str) -> Path:
    """Return a validated absolute directory path."""
    path = Path(directory_path).resolve()
    if not path.is_dir():
        raise typer.BadParameter("must be an existing directory")
    return path


echo_success = functools.partial(typer.secho, fg=typer.colors.GREEN, bold=True)
echo_error = functools.partial(typer.secho, fg=typer.colors.RED, err=True, bold=True)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress info logging."),
) -> None:
    if verbose and quiet:
        raise typer.BadParameter("cannot use --verbose and --quiet together")

    pkg_name = fops.__name__
    pkg_version = typer.style(fops.__version__, fg=typer.colors.CYAN)

    if version:
        typer.echo(f"{pkg_name} {pkg_version}")
        raise typer.Exit(code=ExitCode.SUCCESS)

    if ctx.invoked_subcommand is None:
        typer.echo(f"{pkg_name} {pkg_version} ready. See --help for usage.")
        raise typer.Exit(code=ExitCode.SUCCESS)

    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    setup_logging(level)


@create.command()
def archive(
    directory_path: Annotated[
        Path,
        typer.Argument(
            help="Directory to process.",
            show_default="cwd",
            default_factory=lambda: Path.cwd(),
            callback=validate_directory_path,
        ),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            help="Archive name.",
            show_default="utc_timestamp_dirname",
        ),
    ] = None,
    fmt: str = typer.Option("zip", help="Archive format."),
    pattern: Annotated[
        list[str] | None, typer.Option(help="File pattern to include.")
    ] = None,
) -> None:
    """Archive files in the target directory.

    Example:
    $ fops create archive
    $ fops create archive some_dir
    $ fops create archive --name archive
    $ fops create archive --fmt gztar
    $ fops create archive --pattern '*.txt' --pattern '*.md'
    """
    try:
        archive_path = core.create_archive(directory_path, pattern, name, fmt)
        echo_success(f"done: created {archive_path}")
    except Exception as exc:
        message = "cannot create archive"
        logger.exception(message)
        echo_error(f"error: {message}")
        raise typer.Exit(code=ExitCode.ERROR) from exc


@delete.command()
def branches(
    refs: bool = typer.Option(
        False, "--refs", help="Delete remote-tracking git branch refs as well."
    ),
    protect: Annotated[
        list[str] | None, typer.Option(help="Branch to protect from deletion.")
    ] = None,
) -> None:
    """Delete local git branches and remote-tracking refs except protected ones.

    Example:
    $ fops delete branches
    $ fops delete branches --refs
    $ fops delete branches --protect some_branch --protect another_branch
    """
    try:
        current = core.get_current_branch()
        protected = PROTECTED_BRANCHES.union(current).union(protect or {})

        num_deleted_branches = core.delete_local_branches(protected)
        branch_label = "branch" if num_deleted_branches == 1 else "branches"
        message = f"done: deleted {num_deleted_branches} {branch_label}"

        if refs:
            num_deleted_refs = core.delete_remote_branch_refs(protected)
            ref_label = "ref" if num_deleted_refs == 1 else "refs"
            message += f", deleted {num_deleted_refs} {ref_label}"

        echo_success(message)

    except Exception as exc:
        message = "cannot delete branches"
        logger.exception(message)
        echo_error(f"error: {message}")
        raise typer.Exit(code=ExitCode.ERROR) from exc


@delete.command()
def cache(
    directory_path: Annotated[
        Path,
        typer.Argument(
            help="Directory to process.",
            show_default="cwd",
            default_factory=lambda: Path.cwd(),
            callback=validate_directory_path,
        ),
    ],
    dp: Annotated[
        list[str] | None, typer.Option(help="Directory pattern to include.")
    ] = None,
    fp: Annotated[
        list[str] | None, typer.Option(help="File pattern to include.")
    ] = None,
) -> None:
    """Delete cache directories and files in the specified directory.

    Example:
    $ fops delete cache
    $ fops delete cache some_dir
    $ fops delete cache --dp '*.egg-info'
    $ fops delete cache --dp '*.egg-info' --fp '*.cache'
    """
    cache_dir_patterns = CACHE_DIR_PATTERNS.union(dp or {})
    cache_file_patterns = CACHE_FILE_PATTERNS.union(fp or {})

    try:
        logger.info("deleting cache in directory: %s", directory_path)
        num_deleted = core.delete_cache_dirs(directory_path, cache_dir_patterns)
        num_deleted += core.delete_cache_files(directory_path, cache_file_patterns)

        item_label = "item" if num_deleted == 1 else "items"
        message = f"done: deleted {num_deleted} {item_label}"

        echo_success(message)

    except Exception as exc:
        message = "cannot delete cache"
        logger.exception(message)
        echo_error(f"error: {message}")
        raise typer.Exit(code=ExitCode.ERROR) from exc


@rename.command()
def extensions(
    cur: Annotated[
        str,
        typer.Argument(help="Current file extension to match (e.g. 'txt' or '.txt')."),
    ],
    new: Annotated[
        str,
        typer.Argument(help="New file extension to change to (e.g. 'md' or '.md')."),
    ],
    directory_path: Annotated[
        Path,
        typer.Argument(
            help="Directory to process.",
            show_default="cwd",
            default_factory=lambda: Path.cwd(),
            callback=validate_directory_path,
        ),
    ],
    copy: bool = typer.Option(
        False, "--copy", help="Copy files instead of modify them."
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="Process files recursively in subdirectories."
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing target files if they already exist.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be changed without modifying any files.",
    ),
) -> None:
    """Rename file extensions in the target directory.

    Example:
    $ fops rename extensions --copy --recursive .txt .md --dry-run
    """
    try:
        core.rename_extensions(
            directory_path,
            old_ext=cur,
            new_ext=new,
            create_copy=copy,
            recursive=recursive,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        echo_success("done")
    except Exception as exc:
        message = "cannot rename"
        logger.exception(message)
        echo_error(f"error: {message}")
        raise typer.Exit(code=ExitCode.ERROR) from exc
