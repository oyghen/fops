import sys


def main() -> None:
    try:
        from fops import cli
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            "CLI dependencies missing. Use: uv tool install 'fops[cli]'",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    cli.main()
