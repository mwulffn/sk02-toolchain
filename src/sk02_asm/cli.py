"""Command-line interface for the SK-02 assembler."""

import argparse
import sys
from pathlib import Path

from .assembler import Assembler, assemble_file


def main():
    """Main entry point for the assembler CLI."""
    parser = argparse.ArgumentParser(
        description="SK-02 8-bit Computer Assembler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s program.asm                    # Output: program.bin
  %(prog)s program.asm -o output.bin      # Specify output file
  %(prog)s program.asm -f hex             # Output Intel HEX format
  %(prog)s program.asm -l program.lst     # Generate listing file
  %(prog)s program.asm --org 0x9000       # Set origin address
  %(prog)s program.asm -I lib/            # Add include search path
        """,
    )

    parser.add_argument("input", type=str, help="Input assembly file (.asm)")

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file (default: input with .bin or .hex extension)",
    )

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["bin", "hex"],
        default="bin",
        help="Output format: bin (binary) or hex (Intel HEX) (default: bin)",
    )

    parser.add_argument(
        "-l",
        "--listing",
        type=str,
        default=None,
        help="Generate assembly listing file",
    )

    parser.add_argument(
        "--org",
        type=str,
        default="0x8000",
        help="Origin address (default: 0x8000)",
    )

    parser.add_argument(
        "-I",
        "--include",
        type=str,
        action="append",
        default=[],
        help="Add include search path (can be used multiple times)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Parse origin address
    try:
        if args.org.startswith("0x") or args.org.startswith("0X"):
            start_address = int(args.org, 16)
        elif args.org.startswith("$"):
            start_address = int(args.org[1:], 16)
        else:
            start_address = int(args.org)
    except ValueError:
        print(f"Error: Invalid origin address: {args.org}", file=sys.stderr)
        sys.exit(1)

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Build include paths
    include_paths = [Path(p) for p in args.include]

    # Assemble
    if args.verbose:
        print(f"Assembling {args.input}...")
        print(f"Origin: ${start_address:04X}")
        print(f"Format: {args.format}")
        if include_paths:
            print(f"Include paths: {', '.join(str(p) for p in include_paths)}")

    success = assemble_file(
        args.input, args.output, args.format, start_address, include_paths
    )

    # Generate listing if requested
    if args.listing and success:
        with open(input_path, "r") as f:
            source = f.read()
        assembler = Assembler(source, start_address, input_path, include_paths)
        output, _ = assembler.assemble()
        listing = output.get_listing()
        with open(args.listing, "w") as f:
            f.write(listing)
        if args.verbose:
            print(f"Listing written to {args.listing}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
