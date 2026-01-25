# SK-02 Processor Simulator

A text-based simulator for the SK-02 8-bit processor that can execute compiled binary files and provide interactive debugging capabilities.

## Features

- **Full instruction set support**: All 214 opcodes implemented
- **Interactive debugger**: Step through code, set breakpoints, examine memory and registers
- **Batch mode**: Run programs non-interactively for testing
- **Disassembler**: View disassembled code at any address
- **Memory subsystem**: 64KB address space with RAM/ROM regions
- **I/O simulation**: GPIO, display outputs (OUT_0, OUT_1), and inputs (X, Y)
- **Hardware stacks**: Separate return and data stacks

## Architecture

The SK-02 simulator implements:

- **8 registers**: A, B, C, D, E, F, G, H (8-bit each)
- **4 register pairs**: AB, CD, EF, GH (16-bit)
- **64KB address space**:
  - RAM: $0000-$3FFF (16KB)
  - ROM: $8000-$FFFF (32KB)
- **Two hardware stacks**:
  - Return address stack (for GOSUB/RETURN)
  - General purpose data stack (for PUSH/POP)
- **Flags**: Zero, Overflow, Interrupt
- **I/O ports**: GPIO, OUT_0, OUT_1, X, Y

## Installation

The simulator is already included in the project. No additional installation needed.

## Usage

### Batch Mode

Run a program non-interactively:

```bash
# Using uv
uv run python -m simulator program.bin --run

# Using the convenience script
./sk02-sim program.bin --run
```

### Interactive Mode

Load a program and debug interactively:

```bash
# Start with a program loaded
uv run python -m simulator program.bin

# Or start empty and load later
uv run python -m simulator
```

### Command Line Options

```
usage: simulator [-h] [--org ORG] [--run] [binary]

positional arguments:
  binary               Binary file to load

options:
  --org, --origin ORG  Load address (default: 0x8000)
  --run                Run immediately and exit (batch mode)
```

## Interactive Commands

Once in the simulator, use these commands:

### Program Control

- `load <file> [org]` - Load binary file at address (default: $8000)
- `run` - Run until HALT or breakpoint
- `step [n]` - Execute n instructions (default: 1)
- `reset` - Reset CPU to initial state

### Debugging

- `break <addr>` - Set breakpoint at address
- `clear <addr>` - Clear breakpoint at address
- `regs` - Show all registers and flags
- `mem <addr> [len]` - Dump memory region (default: 64 bytes)
- `disasm <addr> [n]` - Disassemble n instructions (default: 10)
- `set <reg> <val>` - Set register value

### I/O

- `io` - Show I/O register status (GPIO, OUT_0, OUT_1, X, Y)

### Other

- `help` - Show help message
- `quit` - Exit simulator

### Address/Value Formats

- Hexadecimal: `$1234` or `0x1234`
- Decimal: `1234`

## Examples

### Running the Simple Test

```bash
./sk02-sim examples/simple.bin --run
```

Output:
```
Loaded 14 bytes from examples/simple.bin at $8000

Starting execution...
CPU halted
Executed 52 instructions

Final state:
PC: $800E  RSP: 00  DSP: 00  Flags: Z=1 O=0 I=0
A=$0A B=$0A C=$00 D=$00 E=$00 F=$00 G=$00 H=$00
AB=$0A0A CD=$0000 EF=$0000 GH=$0000

GPIO:  $00
OUT_0: $0A
OUT_1: $00
```

### Interactive Debugging Session

```bash
$ ./sk02-sim examples/simple.bin
Loaded 14 bytes from examples/simple.bin at $8000

SK-02 Simulator
Type 'help' for commands

> disasm 0x8000 8
$8000: SET_A        $00
$8002: A++
$8003: SET_B        $0A
$8005: CMP
$8006: JMP_ZERO     $800C
$8009: JMP          $8002
$800C: A>OUT_0
$800D: HALT

> step 3
$8000: SET_A        $00
$8002: A++
$8003: SET_B        $0A

> regs
PC: $8005  RSP: 00  DSP: 00  Flags: Z=0 O=0 I=0
A=$01 B=$0A C=$00 D=$00 E=$00 F=$00 G=$00 H=$00
AB=$0A01 CD=$0000 EF=$0000 GH=$0000

> break 0x800C
Breakpoint set at $800C

> run
Breakpoint hit at $800C

> regs
PC: $800C  RSP: 00  DSP: 00  Flags: Z=1 O=0 I=0
A=$0A B=$0A C=$00 D=$00 E=$00 F=$00 G=$00 H=$00

> step
$800C: A>OUT_0

> io
GPIO:  $00
OUT_0: $0A
OUT_1: $00

> quit
Goodbye!
```

## Module Structure

```
simulator/
├── __init__.py      # Package initialization
├── cpu.py           # CPU core: registers, flags, execution control
├── memory.py        # Memory subsystem: RAM, ROM, I/O mapping
├── opcodes.py       # Opcode execution and disassembler
├── ui.py            # Interactive text UI
└── __main__.py      # Entry point and CLI
```

## Testing

Create a simple test program:

```assembly
; test.asm
        .ORG $8000

        SET_A #42
        SET_B #10
        ADD
        A>OUT_0
        HALT
```

Assemble and run:

```bash
uv run python -m sk02_asm test.asm -o test.bin
./sk02-sim test.bin --run
```

Expected output:
- OUT_0 should show $34 (52 decimal = 42 + 10)

## Implementation Details

### Instruction Execution

The simulator fetches and decodes instructions based on the opcode definitions in `src/sk02_asm/opcodes.py`. Each instruction is executed in the `execute_opcode()` function in `simulator/opcodes.py`.

### Memory Model

- Little-endian byte order (low byte at lower address)
- ROM region ($8000-$FFFF) is loaded from binary files
- RAM region ($0000-$3FFF) is initialized to zero
- I/O ports are memory-mapped

### Stack Behavior

- Two separate 256-entry stacks with 8-bit pointers
- Return stack: Used by GOSUB/RETURN for call addresses
- Data stack: Used by PUSH/POP for general data

### Flags

- **Zero**: Set when result is zero
- **Overflow**: Set on arithmetic overflow/underflow
- **Interrupt**: Hardware interrupt flag (not fully implemented)

## Limitations

- No cycle-accurate timing simulation
- Hardware interrupts not fully implemented
- No peripheral device simulation beyond basic I/O ports
- Maximum 1,000,000 instructions per run (configurable in code)

## Future Enhancements

Potential improvements:

- Cycle counting for performance analysis
- Watch expressions for advanced debugging
- Trace logging to file
- Memory access visualization
- Configurable I/O device simulation
- Script-based automated testing

## Workflow Integration

### From Assembly to Simulation

```bash
# Write assembly
cat > test.asm << 'EOF'
        .ORG $8000
        SET_A #42
        A>OUT_0
        HALT
EOF

# Assemble
uv run python -m sk02_asm test.asm -o test.bin

# Simulate
./sk02-sim test.bin --run
```

### From C to Simulation

```bash
# Write C code
cat > test.c << 'EOF'
void main() {
    char x = 42;
    // Output will depend on compiler implementation
}
EOF

# Compile to assembly
uv run sk02cc test.c

# Assemble
uv run python -m sk02_asm test.asm -o test.bin

# Simulate
./sk02-sim test.bin --run
```

### Complete Build and Test Script

```bash
#!/bin/bash
# Build and test a program

set -e

SRC=$1
BASE=$(basename "$SRC" .asm)

echo "Assembling $SRC..."
uv run python -m sk02_asm "$SRC" -o "${BASE}.bin" -l "${BASE}.lst"

echo "Running in simulator..."
./sk02-sim "${BASE}.bin" --run

echo "Done!"
```

## Debugging Tips

### Finding Infinite Loops

If your program runs for 1,000,000 instructions without halting:

```bash
# Run in interactive mode
./sk02-sim program.bin

> run
Execution stopped after 1000000 instructions

> regs
PC: $8042  RSP: 00  DSP: 00  ...

> disasm 0x8042 5
# Check what code is at PC to see where it's stuck
```

### Tracing Execution

```bash
> load program.bin
> break 0x8000  # Start of program
> run
Breakpoint hit at $8000

> step 10  # Watch first 10 instructions execute
> regs     # Check state
```

### Checking Memory

```bash
> mem 0x4000 32  # Check RAM contents
> mem 0x8000 32  # Check ROM contents
```

### Monitoring I/O

```bash
> step 5
> io  # Check outputs after each few steps
```

## Troubleshooting

### "Unknown opcode"

The binary file contains an invalid opcode. This could mean:
- Binary file is corrupted
- Binary was not assembled correctly
- Wrong file loaded

### "File not found"

Check that the binary file exists and path is correct:

```bash
ls -lh program.bin
```

### Program doesn't halt

Some programs may not have a HALT instruction. Use Ctrl+C or set a breakpoint to stop execution.

### Wrong output values

Check the disassembly to verify the program is doing what you expect:

```bash
./sk02-sim program.bin
> disasm 0x8000 20
```
