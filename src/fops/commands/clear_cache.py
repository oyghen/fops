from pathlib import Path

import typer

import fops
from fops.commands import app


@app.command()
def clear_cache() -> None:
    try:
        fops.core.clear_cache(directory_path=Path.cwd())
        typer.secho("Cache cleared.", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho("Failed to clear cache.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
