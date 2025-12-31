import logging
from pathlib import Path

import typer

import fops
from fops.cli import app

logger = logging.getLogger(__name__)


@app.command()
def delete_cache() -> None:
    """Delete cache directories and files."""
    try:
        fops.core.delete_cache(directory_path=Path.cwd())
        typer.secho("Done.", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to delete cache"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
