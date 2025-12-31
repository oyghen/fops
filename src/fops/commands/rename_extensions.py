import logging
from pathlib import Path

import typer

import fops
from fops.cli import app

logger = logging.getLogger(__name__)

DIRECTORY_ARG = typer.Argument(help="Directory to process.")
OLD_EXT_ARG = typer.Argument(help="File extension to match (e.g. 'txt' or '.txt').")
NEW_EXT_ARG = typer.Argument(help="New file extension to apply (e.g. 'md' or '.md').")

CREATE_COPY_OPT = typer.Option(False, help="Copy files instead of renaming them.")
RECURSIVE_OPT = typer.Option(False, help="Process files recursively in subdirectories.")
OVERWRITE_OPT = typer.Option(
    False, help="Overwrite existing target files if they already exist."
)
DRY_RUN_OPT = typer.Option(
    False, help="Show what would be changed without modifying any files."
)


@app.command()
def rename_extensions(
    directory_path: Path = DIRECTORY_ARG,
    old_ext: str = OLD_EXT_ARG,
    new_ext: str = NEW_EXT_ARG,
    create_copy: bool = CREATE_COPY_OPT,
    recursive: bool = RECURSIVE_OPT,
    overwrite: bool = OVERWRITE_OPT,
    dry_run: bool = DRY_RUN_OPT,
) -> None:
    """Rename (or copy) files in a directory by changing their extensions.

    Example:
    $ fops rename-extensions --create-copy --recursive . .txt .md --dry-run
    """
    directory = Path(directory_path).resolve()

    if not directory.exists():
        typer.secho(f"Directory not found: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    if not directory.is_dir():
        typer.secho(f"Not a directory: {directory}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        fops.core.rename_extensions(
            directory,
            old_ext,
            new_ext,
            create_copy=create_copy,
            recursive=recursive,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        typer.secho("Done.", fg=typer.colors.GREEN)
    except Exception as exc:
        message = "Failed to rename extensions"
        logger.exception(message)
        typer.secho(f"{message} (see log for details).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
