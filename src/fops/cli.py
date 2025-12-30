import logging
import sys
from pathlib import Path

import typer

import fops

app = typer.Typer(add_completion=False)

DIRECTORY_ARG = typer.Argument(None, help="Directory to archive (cwd if not provided).")

ARCHIVE_NAME_OPT = typer.Option(None, help="Archive name.")
PATTERNS_OPT = typer.Option(None, help="File patterns to include.")
ARCHIVE_FORMAT_OPT = typer.Option("zip", help="Archive format.")


def configure_logging(level: int) -> None:
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    fmt = "%(levelname)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    root.addHandler(handler)
    root.setLevel(level)


@app.callback(invoke_without_command=True)
def cli(
    version: bool = typer.Option(
        False, "--version", "-V", help="Show app version and exit."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress info logging."),
) -> None:
    if version:
        typer.echo(f"{fops.__name__} {fops.__version__}")
        raise typer.Exit()

    if verbose and quiet:
        raise typer.BadParameter("Cannot use --verbose and --quiet together")

    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    configure_logging(level)


@app.command()
def clear_cache() -> None:
    try:
        fops.core.clear_cache(directory_path=Path.cwd())
        typer.secho("Cache cleared.", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho("Failed to clear cache.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def create_archive(
    directory_path: Path | None = DIRECTORY_ARG,
    archive_name: str | None = ARCHIVE_NAME_OPT,
    patterns: list[str] | None = PATTERNS_OPT,
    archive_format: str = ARCHIVE_FORMAT_OPT,
) -> None:
    """Archive files."""
    directory = directory_path or Path.cwd()

    if not directory.exists():
        typer.secho(f"Directory not found: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    if not directory.is_dir():
        typer.secho(f"Not a directory: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        archive_path = fops.core.create_archive(
            directory,
            archive_name,
            patterns,
            archive_format,
        )
        typer.secho(f"Archive created - {archive_path}", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho("Failed to create archive.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


def main() -> None:
    """Canonical entry point for CLI execution."""
    app()
