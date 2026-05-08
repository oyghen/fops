#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "purekit",
#   "typer",
# ]
# ///

import subprocess
import tomllib
from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated

import purekit as pk  # type: ignore
import typer  # type: ignore

ROOT = Path(__file__).resolve().parent
ROOT_PYPROJECT = ROOT / "pyproject.toml"


class BumpType(StrEnum):
    """Supported version bump types."""

    major = auto()
    minor = auto()
    patch = auto()
    stable = auto()
    alpha = auto()
    beta = auto()
    rc = auto()
    post = auto()
    dev = auto()


def main(
    bump_types: Annotated[
        list[BumpType], typer.Option("--bump", help="Specify bump type.")
    ],
) -> None:
    """Bump versions for lockstep release.

    Example:
    $ uv run version.py --bump minor
    $ uv run version.py --bump minor --bump rc
    $ uv run version.py --bump rc
    $ uv run version.py --bump stable
    """
    bump_versions(bump_types)
    bumped_version = project_version(ROOT_PYPROJECT)
    refresh_lockfile()
    commit_bump(bumped_version)
    tag_commit(bumped_version)
    typer.echo(pk.text.headline(typer.style("if successful", fg=typer.colors.YELLOW)))
    typer.echo("git push && git push --tags")


def bump_versions(bumps: list[BumpType]) -> None:
    """Bump the workspace root and package versions in one uv-style sequence."""
    run(*uv_version_args(bumps))


def uv_version_args(bumps: list[BumpType], package: str | None = None) -> list[str]:
    """Build a uv version command that preserves bump order."""
    args = ["uv", "version", "--frozen"]

    for bump in bumps:
        args.extend(["--bump", bump.value])

    if package is not None:
        args.extend(["--package", package])

    return args


def project_version(path: Path) -> str:
    """Read the project version from a pyproject.toml file."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data["project"]["version"]


def refresh_lockfile() -> None:
    """Regenerate the uv lockfile."""
    run("uv", "lock")


def commit_bump(version: str) -> None:
    """Stage changed files and commit the version bump."""
    prefix = typer.style("Created commit", fg=typer.colors.GREEN, bold=True)
    message = f"chore(release): bump version to v{version}"

    # Stage only the files this script mutates
    files = (ROOT_PYPROJECT, "uv.lock")
    for file_name in files:
        run("git", "add", str(file_name))

    run("git", "commit", "-m", message)

    typer.echo(f"{prefix} {message}")


def tag_commit(version: str) -> None:
    """Create an annotated release tag for the version."""
    prefix = typer.style("Created tag", fg=typer.colors.GREEN, bold=True)
    tag = f"v{version}"

    run("git", "tag", "-a", tag, "-m", tag)

    typer.echo(f"{prefix} {tag}")


def run(*args: str) -> None:
    """Run a command in the repository root."""
    subprocess.run(args, check=True, cwd=ROOT)


if __name__ == "__main__":
    typer.run(main)
