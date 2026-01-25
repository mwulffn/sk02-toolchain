"""Command-line interface for SK02-C compiler."""

import argparse
import sys

from .compiler import compile_file


def main() -> None:
    """Main entry point for SK02-C compiler."""
    parser = argparse.ArgumentParser(
        description="SK02-C - C compiler for SK-02 8-bit computer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  sk02cc program.c               Compile to program.asm
  sk02cc program.c -o output.asm Specify output file
  sk02cc --version               Show version

The compiler generates SK-02 assembly (.asm) which can then be
assembled using the sk02-asm assembler to produce binary output.
        """,
    )

    parser.add_argument("input", help="Input C source file (.c)")
    parser.add_argument(
        "-o", "--output", help="Output assembly file (.asm)", default=None
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--version", action="version", version="SK02-C compiler 0.1.0"
    )

    args = parser.parse_args()

    # Compile
    success = compile_file(args.input, args.output)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
