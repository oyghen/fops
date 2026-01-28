import logging
from pathlib import Path

import typer

import fops
from fops.cli import app

logger = logging.getLogger(__name__)

DIRECTORY_ARG = typer.Argument(help="Directory to process.")


@app.command()
def delete_cache(directory_path: Path = DIRECTORY_ARG) -> None:
    """Delete cache directories and files.

    Example:
    $ fops delete-cache .
    """
    directory = Path(directory_path).resolve()

    if not directory.exists():
        typer.secho(f"Directory not found: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    if not directory.is_dir():
        typer.secho(f"Not a directory: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        fops.core.delete_cache(directory_path=directory)
        typer.secho("Done.", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to delete cache"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
