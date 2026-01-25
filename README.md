# SK-02 Development Tools

A complete development toolchain for the SK-02 8-bit homebrew computer:
- **SK02-C Compiler** - C subset compiler (Phase 1 complete)
- **SK-02 Assembler** - Full-featured assembler with 214 opcodes
- **SK-02 Simulator** - Interactive debugger and execution simulator

## Features

- **214 opcodes** - Full instruction set (0-127 simple, 128-254 extended)
- **8 registers** - A, B, C, D, E, F, G, H (can be paired for 16-bit operations)
- **6502-style syntax** - Familiar assembly language conventions
- **Multiple output formats** - Binary and Intel HEX
- **Label support** - Global and local labels with scoping
- **Assembler directives** - .ORG, .EQU, .BYTE, .WORD, .ASCII, .ASCIIZ
- **Two-pass assembly** - Forward references supported
- **Little-endian** - Address format (low byte first)

## Installation

```bash
uv sync
```

## Quick Start

### C Compiler

```bash
# Easy way: Use the build script (C to binary in one step)
./sk02-build examples/hello.c

# Quiet mode (no prompts, auto-cleanup)
./sk02-build-quiet examples/hello.c examples/hello.bin

# For simulator: C to simulator text format
./sk02-build-sim examples/hello.c examples/hello.txt

# Manual way: Compile C to assembly
uv run sk02cc examples/hello.c

# Then assemble to binary
uv run sk02-asm examples/hello.asm -o examples/hello.bin

# Convert binary to simulator format
./bin2sim examples/hello.bin -o examples/hello.txt
```

See [docs/compiler-usage.md](docs/compiler-usage.md) for complete compiler documentation.

### Supported C Features (Phase 1)
- Types: `char`, `int`, `char*`, `int*`
- Operators: arithmetic, bitwise, comparison, logical
- Control: `if/else`, `while`, `for`, `break`, `continue`, `return`
- Functions: non-recursive, max 2 int params
- Variables: global (local variables in Phase 2)

**Important**: No recursion, no structs, no preprocessor. See feasibility doc for details.

### Simulator

```bash
# Run a program in batch mode
./sk02-sim examples/simple.bin --run

# Interactive debugging
./sk02-sim examples/simple.bin

# Or use Python module directly
uv run python -m simulator examples/simple.bin

# Interactive commands:
#   step [n]       - Execute n instructions
#   run            - Run until HALT or breakpoint
#   break <addr>   - Set breakpoint
#   regs           - Show registers
#   mem <addr>     - Show memory
#   disasm <addr>  - Disassemble code
#   io             - Show I/O status
#   help           - Show all commands
```

See [docs/simulator.md](docs/simulator.md) for complete simulator documentation.

## Assembler Usage

### Command Line

```bash
# Basic assembly (output: program.bin)
uv run python -m sk02_asm program.asm

# Specify output file
uv run python -m sk02_asm program.asm -o output.bin

# Generate Intel HEX format
uv run python -m sk02_asm program.asm -f hex

# Generate assembly listing
uv run python -m sk02_asm program.asm -l program.lst

# Set origin address
uv run python -m sk02_asm program.asm --org 0x9000

# Verbose output
uv run python -m sk02_asm program.asm -v
```

### Python API

```python
from sk02_asm import assemble_file

# Assemble a file
success = assemble_file('program.asm', 'output.bin', format='bin')
```

## Assembly Syntax

### Number Formats

- Hexadecimal: `$FF` or `$1234`
- Binary: `%10101010`
- Decimal: `255` or `42`
- Character: `'A'` (ASCII value)

### Labels

```asm
START:              ; Global label
    NOP
.loop:              ; Local label (scoped to START)
    A++
    JMP .loop       ; Reference local label
```

### Instructions

```asm
; Implied addressing (1 byte)
NOP
A++
HALT

; 8-bit immediate (2 bytes)
SET_A #$42
SET_B #100

; 16-bit immediate (3 bytes)
SET_AB #$1234
SET_CD #$5678

; 16-bit address (3 bytes)
LOAD_A $4000
STORE_A $4001
JMP START
GOSUB SUBROUTINE
```

### Directives

```asm
.ORG $8000          ; Set origin address (default: $8000)
.EQU DELAY, $FF     ; Define constant
.BYTE $00, $FF, 42  ; Define bytes
.WORD $8000, START  ; Define 16-bit words (little-endian)
.ASCII "HELLO"      ; ASCII string (no null terminator)
.ASCIIZ "WORLD"     ; ASCII string with null terminator
```

## Instruction Set Summary

### Data Movement (1 byte)
- `0>A`, `1>A`, `FF>A` - Load constants into A
- `A>B`, `B>A`, `C>D`, etc. - Register-to-register moves
- `PUSH_A`, `POP_A`, `PUSH_B`, `POP_B` - Stack operations

### Arithmetic (1 byte)
- `A++`, `A--`, `B++`, `B--` - Increment/decrement
- `ADD`, `SUB` - A = A + B, A = A - B
- `ADD_c`, `SUB_c` - With carry
- `AB++`, `AB--`, `CD++`, `CD--` - 16-bit increment/decrement
- `AB+CD`, `AB-CD` - 16-bit arithmetic

### Logical (1 byte)
- `NOT`, `AND`, `OR`, `XOR`, `NAND`, `NOR`, `NXOR`

### Shift (1 byte)
- `A>>`, `A<<`, `B>>`, `B<<` - Logical shifts
- `AB>>`, `AB<<` - 16-bit shifts
- `S_A>>`, `S_B>>` - Arithmetic shifts (sign-preserving)

### Comparison (1 byte)
- `CMP` - Compare A and B (sets flags)
- `CMP_16` - Compare AB and CD (16-bit)
- `A_ZERO`, `AB_ZERO` - Test for zero

### Memory (3 bytes for absolute, 1 byte for register-indirect)
- `LOAD_A addr`, `LOAD_B addr` - Load from memory
- `STORE_A addr`, `STORE_B addr` - Store to memory
- `LOAD_A_CD`, `LOAD_B_CD` - Load using CD as address pointer
- `LOAD_A_EF`, `LOAD_A_GH` - Load using EF or GH as pointer
- `LO_A_CD++`, `ST_A_CD++` - Auto-increment pointer versions

### Control Flow (3 bytes)
- `JMP addr` - Unconditional jump
- `JMP_ZERO addr`, `JMP_OVER addr` - Conditional jumps based on flags
- `JMP_A_POS addr`, `JMP_A_EVEN addr` - Conditional jumps based on A
- `GOSUB addr`, `RETURN` - Subroutine calls
- `JMP_COMP`, `GOSUB_COMP` - Computed jumps (address in AB)

### I/O (1 byte)
- `A>OUT_0`, `A>OUT_1` - Output to 7-segment displays
- `A>GPIO`, `GPIO>A` - General purpose I/O
- `X>A`, `Y>A` - Read input devices

### System (1 byte, some 2-3 bytes)
- `HALT` - Stop execution
- `NOP` - No operation
- `SET_IV #addr` - Set interrupt vector (3 bytes)
- `TRG_HWI`, `CLEAR_HWI` - Hardware interrupt control

## Examples

See the `examples/` directory for sample programs:
- `hello.asm` - Comprehensive example demonstrating various features
- `simple.asm` - Simple counter program

## Architecture

The SK-02 assembler uses a two-pass architecture:

**Pass 1**: Build symbol table
- Parse source code
- Record label addresses
- Calculate instruction sizes
- Process .EQU directives

**Pass 2**: Generate machine code
- Resolve label references
- Generate opcodes and operands
- Handle directives (.BYTE, .WORD, etc.)
- Output binary or Intel HEX

## License

See LICENSE file for details.
