"""Text-based UI for SK-02 simulator."""

from pathlib import Path

from .cpu import CPU
from .memory import Memory
from .opcodes import disassemble


class SimulatorUI:
    """Interactive debugger UI for SK-02 simulator."""

    def __init__(self):
        """Initialize simulator UI."""
        self.memory = Memory()
        self.cpu = CPU(self.memory)
        self.breakpoints: set[int] = set()
        self.running = True

    def load_binary(self, filepath: str, origin: int = 0x8000) -> None:
        """Load binary file into memory."""
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}")
            return

        data = path.read_bytes()
        self.memory.load_binary(data, origin)
        self.cpu.PC = origin
        print(f"Loaded {len(data)} bytes from {filepath} at ${origin:04X}")

    def show_registers(self) -> None:
        """Display all register values."""
        print(self.cpu.get_register_display())

    def show_memory(self, addr: int, length: int = 64) -> None:
        """Display memory dump."""
        print(self.memory.dump(addr, length))

    def set_register(self, reg: str, value: int) -> None:
        """Set register value."""
        reg = reg.upper()
        if hasattr(self.cpu, reg):
            setattr(self.cpu, reg, value & 0xFFFF)
            print(f"{reg} = ${value:04X}")
        else:
            print(f"Error: Unknown register: {reg}")

    def step(self, count: int = 1) -> None:
        """Execute n instructions."""
        for i in range(count):
            if self.cpu.halted:
                print("CPU halted")
                break

            # Show current instruction
            disasm = disassemble(self.cpu, self.cpu.PC, 1)
            if disasm:
                print(disasm[0])

            # Execute
            try:
                self.cpu.step()
            except Exception as e:
                print(f"Error executing instruction: {e}")
                break

            # Check breakpoint
            if self.cpu.PC in self.breakpoints:
                print(f"Breakpoint hit at ${self.cpu.PC:04X}")
                break

    def run_until_halt(self, max_instructions: int = 1000000) -> None:
        """Run until HALT or breakpoint."""
        for _ in range(max_instructions):
            if self.cpu.halted:
                print("CPU halted")
                break

            if self.cpu.PC in self.breakpoints:
                print(f"Breakpoint hit at ${self.cpu.PC:04X}")
                break

            try:
                self.cpu.step()
            except Exception as e:
                print(f"Error at PC=${self.cpu.PC:04X}: {e}")
                break
        else:
            print(f"Execution stopped after {max_instructions} instructions")

        print(f"Executed {self.cpu.instruction_count} instructions")

    def disassemble_at(self, addr: int, count: int = 10) -> None:
        """Disassemble instructions at address."""
        lines = disassemble(self.cpu, addr, count)
        for line in lines:
            print(line)

    def add_breakpoint(self, addr: int) -> None:
        """Add breakpoint at address."""
        self.breakpoints.add(addr)
        print(f"Breakpoint set at ${addr:04X}")

    def clear_breakpoint(self, addr: int) -> None:
        """Clear breakpoint at address."""
        if addr in self.breakpoints:
            self.breakpoints.remove(addr)
            print(f"Breakpoint cleared at ${addr:04X}")
        else:
            print(f"No breakpoint at ${addr:04X}")

    def show_help(self) -> None:
        """Display help message."""
        help_text = """
SK-02 Simulator Commands:
  load <file> [org]   - Load binary file (default org=$8000)
  run                 - Run until HALT/breakpoint
  step [n]            - Execute n instructions (default 1)
  break <addr>        - Set breakpoint at address
  clear <addr>        - Clear breakpoint at address
  regs                - Show all registers
  mem <addr> [len]    - Dump memory (default len=64)
  set <reg> <val>     - Set register value
  reset               - Reset CPU
  disasm <addr> [n]   - Disassemble n instructions (default 10)
  io                  - Show I/O status
  help                - Show this help
  quit                - Exit simulator

Address/value formats: $1234 (hex), 1234 (decimal)
"""
        print(help_text)

    def show_io_status(self) -> None:
        """Display I/O register status."""
        print(f"GPIO:  ${self.memory.gpio:02X}")
        print(f"OUT_0: ${self.memory.out_0:02X}")
        print(f"OUT_1: ${self.memory.out_1:02X}")
        print(f"X:     ${self.memory.x_input:02X}")
        print(f"Y:     ${self.memory.y_input:02X}")

    def parse_value(self, s: str) -> int:
        """Parse hex ($1234) or decimal (1234) value."""
        s = s.strip()
        if s.startswith("$"):
            return int(s[1:], 16)
        elif s.startswith("0x"):
            return int(s, 16)
        else:
            return int(s)

    def handle_command(self, cmd: str, args: list[str]) -> None:
        """Handle a single command."""
        try:
            if cmd == "load":
                if not args:
                    print("Usage: load <file> [origin]")
                    return
                filepath = args[0]
                origin = self.parse_value(args[1]) if len(args) > 1 else 0x8000
                self.load_binary(filepath, origin)

            elif cmd == "run":
                self.run_until_halt()

            elif cmd == "step":
                count = self.parse_value(args[0]) if args else 1
                self.step(count)

            elif cmd == "break":
                if not args:
                    print("Usage: break <addr>")
                    return
                addr = self.parse_value(args[0])
                self.add_breakpoint(addr)

            elif cmd == "clear":
                if not args:
                    print("Usage: clear <addr>")
                    return
                addr = self.parse_value(args[0])
                self.clear_breakpoint(addr)

            elif cmd == "regs":
                self.show_registers()

            elif cmd == "mem":
                if not args:
                    print("Usage: mem <addr> [length]")
                    return
                addr = self.parse_value(args[0])
                length = self.parse_value(args[1]) if len(args) > 1 else 64
                self.show_memory(addr, length)

            elif cmd == "set":
                if len(args) < 2:
                    print("Usage: set <reg> <value>")
                    return
                reg = args[0]
                value = self.parse_value(args[1])
                self.set_register(reg, value)

            elif cmd == "reset":
                self.cpu.reset()
                print("CPU reset")

            elif cmd == "disasm":
                if not args:
                    # Disassemble at current PC
                    addr = self.cpu.PC
                else:
                    addr = self.parse_value(args[0])
                count = self.parse_value(args[1]) if len(args) > 1 else 10
                self.disassemble_at(addr, count)

            elif cmd == "io":
                self.show_io_status()

            elif cmd == "help":
                self.show_help()

            elif cmd in ["quit", "exit", "q"]:
                self.running = False

            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands")

        except ValueError as e:
            print(f"Error: Invalid value - {e}")
        except Exception as e:
            print(f"Error: {e}")

    def run_interactive(self) -> None:
        """Run interactive command loop."""
        print("SK-02 Simulator")
        print("Type 'help' for commands\n")

        while self.running:
            try:
                line = input("> ").strip()
                if not line:
                    continue

                parts = line.split()
                cmd = parts[0].lower()
                args = parts[1:]

                self.handle_command(cmd, args)

            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except EOFError:
                break

        print("\nGoodbye!")

    def run_batch(self, binary_path: str, origin: int = 0x8000) -> None:
        """Run in batch mode - load binary and execute."""
        self.load_binary(binary_path, origin)
        if self.cpu.PC == origin:
            print("\nStarting execution...")
            self.run_until_halt()
            print("\nFinal state:")
            self.show_registers()
            print()
            self.show_io_status()
