import logging
from pathlib import Path

import typer

import fops
from fops.cli import app

logger = logging.getLogger(__name__)

DIRECTORY_ARG = typer.Argument(help="Directory to process.")

ARCHIVE_NAME_OPT = typer.Option(None, help="Archive name.")
PATTERN_OPT = typer.Option(None, help="File pattern to include.")
ARCHIVE_FORMAT_OPT = typer.Option("zip", help="Archive format.")


@app.command()
def create_archive(
    directory_path: Path = DIRECTORY_ARG,
    archive_name: str | None = ARCHIVE_NAME_OPT,
    pattern: list[str] | None = PATTERN_OPT,
    archive_format: str = ARCHIVE_FORMAT_OPT,
) -> None:
    """Archive files.

    Example:
    $ fops create-archive . --pattern '*.txt' --pattern '*.md'
    """
    directory = Path(directory_path).resolve()

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
            pattern,
            archive_format,
        )
        typer.secho(f"Done - {archive_path}", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to create archive"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
