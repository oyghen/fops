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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress info logging."),
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


def setup_logging(level: int) -> None:
    """Set up application logging configuration."""
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    fmt = "[ %(levelname)-8s ] %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    root.addHandler(handler)
    root.setLevel(level)


def validate_directory_path(directory_path: str) -> Path:
    """Return a validated absolute directory path."""
    path = Path(directory_path).resolve()
    if not path.is_dir():
        raise typer.BadParameter("must be an existing directory")
    return path


@app.command()
def create_archive(
    directory_path: Annotated[
        Path,
        typer.Argument(
            help="Directory to process.",
            show_default="cwd",
            default_factory=lambda: Path.cwd(),
            callback=validate_directory_path,
        ),
    ],
    pattern: Annotated[
        list[str] | None, typer.Option(help="File pattern to include.")
    ] = None,
    archive_name: Annotated[str | None, typer.Option(help="Archive name.")] = None,
    archive_format: str = typer.Option("zip", help="Archive format."),
) -> None:
    """Archive files.

    Example:
    $ fops create-archive . --pattern '*.txt' --pattern '*.md'
    """
    try:
        archive_path = core.create_archive(
            directory_path,
            archive_name,
            pattern,
            archive_format,
        )
        typer.secho(f"Done - {archive_path}", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to create archive"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.ERROR) from exc


@app.command()
def delete_branches(
    refs: bool = typer.Option(
        False, "--refs", help="Delete remote-tracking git branch refs as well."
    ),
    protect: Annotated[
        list[str] | None, typer.Option(help="Branch to protect from deletion.")
    ] = None,
) -> None:
    """Delete local git branches and remote-tracking refs except protected ones.

    Example:
    $ fops delete-branches
    $ fops delete-branches --refs
    $ fops delete-branches --protect some_branch --protect another_branch
    """
    try:
        current = core.get_current_branch()
        protected = PROTECTED_BRANCHES.union(current).union(protect or {})

        num_deleted_branches = core.delete_local_branches(protected)
        num_deleted_refs = None
        if refs:
            num_deleted_refs = core.delete_remote_branch_refs(protected)

        parts = []
        if num_deleted_branches:
            branch_label = "branch" if num_deleted_branches == 1 else "branches"
            parts.append(f"deleted {num_deleted_branches} {branch_label}")
        if num_deleted_refs:
            ref_label = "ref" if num_deleted_refs == 1 else "refs"
            parts.append(f"deleted {num_deleted_refs} {ref_label}")

        message = ["done"]
        if parts:
            message.append(", ".join(parts))

        typer.secho(": ".join(message), fg=typer.colors.GREEN, bold=True)

    except Exception as exc:
        message = "cannot delete branches"
        logger.exception(message)
        typer.secho(f"error: {message}", fg=typer.colors.RED, err=True, bold=True)
        raise typer.Exit(code=ExitCode.ERROR) from exc


@app.command()
def delete_cache(
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
    $ fops delete-cache
    $ fops delete-cache some_dir
    $ fops delete-cache --dp '*.egg-info'
    $ fops delete-cache --dp '*.egg-info' --fp '*.cache'
    """
    cache_dir_patterns = CACHE_DIR_PATTERNS.union(dp or {})
    cache_file_patterns = CACHE_FILE_PATTERNS.union(fp or {})

    try:
        num_deleted = core.delete_cache_dirs(directory_path, cache_dir_patterns)
        num_deleted += core.delete_cache_files(directory_path, cache_file_patterns)

        message = "done"
        if num_deleted:
            item_label = "item" if num_deleted == 1 else "items"
            message += f": deleted {num_deleted} {item_label}"

        typer.secho(message, fg=typer.colors.GREEN, bold=True)

    except Exception as exc:
        message = "cannot delete cache"
        logger.exception(message)
        typer.secho(f"error: {message}", fg=typer.colors.RED, err=True, bold=True)
        raise typer.Exit(code=ExitCode.ERROR) from exc


@app.command()
def rename_extensions(
    directory_path: Annotated[
        Path,
        typer.Argument(
            help="Directory to process.",
            show_default="cwd",
            default_factory=lambda: Path.cwd(),
            callback=validate_directory_path,
        ),
    ],
    old_ext: Annotated[
        str, typer.Argument(help="File extension to match (e.g. 'txt' or '.txt').")
    ],
    new_ext: Annotated[
        str, typer.Argument(help="New file extension to apply (e.g. 'md' or '.md').")
    ],
    create_copy: bool = typer.Option(help="Copy files instead of renaming them."),
    recursive: bool = typer.Option(help="Process files recursively in subdirectories."),
    overwrite: bool = typer.Option(
        False, help="Overwrite existing target files if they already exist."
    ),
    dry_run: bool = typer.Option(
        False, help="Show what would be changed without modifying any files."
    ),
) -> None:
    """Rename (or copy) files in a directory by changing their extensions.

    Example:
    $ fops rename-extensions --create-copy --recursive . .txt .md --dry-run
    """
    try:
        core.rename_extensions(
            directory_path,
            old_ext,
            new_ext,
            create_copy=create_copy,
            recursive=recursive,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        typer.secho("Done.", fg=typer.colors.GREEN)
    except Exception as exc:
        logger.exception("failed to rename")
        typer.secho("Failed to rename.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.ERROR) from exc
