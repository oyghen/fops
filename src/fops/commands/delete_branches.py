import logging

import typer

import fops
from fops.cli import app

logger = logging.getLogger(__name__)


@app.command()
def delete_branches() -> None:
    """Delete local git branches and remote-tracking refs except protected ones."""
    try:
        fops.core.delete_local_branches()
        fops.core.delete_remote_branch_refs()
        typer.secho("Done.", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to delete branches"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
