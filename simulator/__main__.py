"""Entry point for SK-02 simulator."""

import argparse
import sys
from pathlib import Path

from .ui import SimulatorUI


def main() -> None:
    """Main entry point for simulator."""
    parser = argparse.ArgumentParser(
        description="SK-02 8-bit Processor Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m simulator program.bin          # Load and run interactively
  python -m simulator program.bin --run    # Load and run to completion
  python -m simulator program.bin --org 0x9000  # Load at custom address
        """,
    )

    parser.add_argument("binary", nargs="?", help="Binary file to load")
    parser.add_argument(
        "--org",
        "--origin",
        type=lambda x: int(x, 0),
        default=0x8000,
        help="Load address (default: 0x8000)",
    )
    parser.add_argument(
        "--run", action="store_true", help="Run immediately and exit (batch mode)"
    )

    args = parser.parse_args()

    ui = SimulatorUI()

    # If binary file provided, load it
    if args.binary:
        if not Path(args.binary).exists():
            print(f"Error: File not found: {args.binary}")
            sys.exit(1)

        if args.run:
            # Batch mode - load, run, show results, exit
            ui.run_batch(args.binary, args.org)
        else:
            # Interactive mode - load then start REPL
            ui.load_binary(args.binary, args.org)
            print()
            ui.run_interactive()
    else:
        # No binary - start interactive mode
        ui.run_interactive()


if __name__ == "__main__":
    main()
