import fops


def main() -> None:
    result = fops.__name__
    expected = "fops"
    if result == expected:
        print(f"Smoke test for {fops.__name__}: PASSED")
    else:
        raise RuntimeError(f"Smoke test for {fops.__name__}: FAILED")


if __name__ == "__main__":
    main()
