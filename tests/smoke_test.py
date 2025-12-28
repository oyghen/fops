import fops


def main():
    result = fops.__name__
    expected = "fops"
    if result == expected:
        print("smoke test passed")
    else:
        raise RuntimeError("smoke test failed")


if __name__ == "__main__":
    main()
