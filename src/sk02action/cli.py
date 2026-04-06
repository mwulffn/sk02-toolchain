"""Command-line interface for the SK-02 Action! compiler."""

import argparse
import sys

from . import __version__
from .compiler import compile_file


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sk02ac",
        description="SK-02 Action! compiler",
    )
    parser.add_argument("input", help="Input .act source file")
    parser.add_argument(
        "-o", "--output", help="Output .asm file (default: input with .asm extension)"
    )
    parser.add_argument(
        "--origin",
        default="$8000",
        help="Code origin address (default: $8000)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    # Parse origin address
    origin_str = args.origin.lstrip("$")
    try:
        origin = int(origin_str, 16)
    except ValueError:
        try:
            origin = int(origin_str)
        except ValueError:
            print(f"Error: Invalid origin address: {args.origin}")
            sys.exit(1)

    success = compile_file(args.input, args.output, origin=origin)
    sys.exit(0 if success else 1)
