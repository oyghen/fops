from pathlib import Path

import typer

import fops
from fops.cli import app

DIRECTORY_ARG = typer.Argument(None, help="Directory to archive (cwd if not provided).")

ARCHIVE_NAME_OPT = typer.Option(None, help="Archive name.")
PATTERNS_OPT = typer.Option(None, help="File patterns to include.")
ARCHIVE_FORMAT_OPT = typer.Option("zip", help="Archive format.")


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
        typer.secho(f"Done - {archive_path}", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho("Failed to create archive.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
