import typer
from rich.console import Console

import fops

console = Console()
app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def version(
    show: bool = typer.Option(
        False, "--version", "-v", help="Show app version and exit."
    ),
) -> None:
    if show:
        typer.echo(f"{fops.__name__} {fops.__version__}")
        raise typer.Exit()


def main() -> None:
    """Canonical entry point for CLI execution."""
    app()
