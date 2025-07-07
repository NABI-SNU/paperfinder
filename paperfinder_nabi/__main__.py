import argparse

from .core import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank recent research papers with Gemini")
    parser.add_argument("--api_key", required=True, help="Google Gemini API key")
    args = parser.parse_args()
    run(args.api_key)


if __name__ == "__main__":
    main()
