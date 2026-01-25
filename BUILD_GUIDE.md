# SK02-C Build Guide

## Quick Reference

```bash
# Build C program to binary (easiest way)
./sk02-build program.c

# Build without prompts
./sk02-build-quiet program.c program.bin

# Build for simulator (C to simulator text format)
./sk02-build-sim program.c program.txt

# Convert existing binary to simulator format
./bin2sim program.bin -o program.txt

# Manual compilation
uv run sk02cc program.c          # C to assembly
uv run sk02-asm program.asm      # Assembly to binary
```

## Build Scripts

### `sk02-build` (Interactive)

The main build script that compiles C to binary with user interaction.

**Features:**
- Compiles .c to .asm using sk02cc
- Assembles .asm to .bin using sk02-asm
- Asks if you want to keep the intermediate .asm file
- Color-coded output
- Shows file sizes

**Usage:**
```bash
./sk02-build program.c              # Creates program.bin
./sk02-build program.c custom.bin   # Creates custom.bin
```

### `sk02-build-quiet` (Non-interactive)

Silent build script for automation and scripting.

**Features:**
- No prompts or questions
- Auto-removes intermediate .asm files
- Perfect for build scripts and makefiles
- Minimal output

**Usage:**
```bash
./sk02-build-quiet program.c                    # Creates program.bin
./sk02-build-quiet program.c output.bin         # Creates output.bin
```

## Manual Build Process

### Step 1: Compile C to Assembly

```bash
uv run sk02cc input.c -o output.asm
```

Options:
- `-o <file>` - Specify output file (default: input.asm)
- `-v` - Verbose output

### Step 2: Assemble to Binary

```bash
uv run sk02-asm output.asm -o program.bin
```

Options:
- `-o <file>` - Output file (default: input.bin)
- `-f hex` - Output Intel HEX format instead of binary
- `-l <file>` - Generate assembly listing
- `--org <addr>` - Set origin address (default: $8000)
- `-v` - Verbose output

## Examples

### Build all examples:

```bash
for f in examples/*.c; do
    ./sk02-build-quiet "$f"
done
```

### Build with listing:

```bash
uv run sk02cc program.c
uv run sk02-asm program.asm -l program.lst -o program.bin
```

### Build for different origin:

```bash
uv run sk02cc program.c
uv run sk02-asm program.asm --org 0x9000 -o program.bin
```

### Generate HEX file:

```bash
uv run sk02cc program.c
uv run sk02-asm program.asm -f hex -o program.hex
```

## File Types

- `.c` - C source code (SK02-C subset)
- `.asm` - SK-02 assembly code
- `.bin` - Raw binary executable
- `.hex` - Intel HEX format
- `.lst` - Assembly listing with addresses

## Troubleshooting

### "Compilation error: ..."

Check your C code follows the SK02-C subset rules:
- See `docs/compiler-usage.md` for supported features
- Common issues:
  - Using unsupported types (float, struct, etc.)
  - Too many function parameters (max 2 int or 4 char)
  - Recursion (not supported)

### "Error: Unknown opcode: ..."

The compiler generated invalid assembly. This is a compiler bug.
Please report it with your C source code.

### "Assembly successful" but program doesn't work

The assembler doesn't validate logic, only syntax. Your program
may have logical errors. Use the listing file (`-l` option) to
debug:

```bash
uv run sk02cc program.c
uv run sk02-asm program.asm -l program.lst -o program.bin
# Check program.lst to see generated addresses and opcodes
```

## Integration with Makefiles

```makefile
%.asm: %.c
\t./sk02-build-quiet $< $@

%.bin: %.asm
\tuv run sk02-asm $< -o $@

all: program.bin

clean:
\trm -f *.asm *.bin *.lst
```

## See Also

- `docs/compiler-usage.md` - Complete compiler documentation
- `docs/c-subset-feasibility.md` - Design rationale
- `docs/calling-convention.md` - Function ABI details
- `README.md` - Project overview
