__all__ = ("app", "main")

import logging
import sys

import typer

import fops

app = typer.Typer(add_completion=False)

# command imports need to be after app creation
from fops.commands import (  # noqa: E402,F401
    create_archive,
    delete_branches,
    delete_cache,
    rename_extensions,
)


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


def main() -> None:
    """Canonical entry point for CLI execution."""
    app()
