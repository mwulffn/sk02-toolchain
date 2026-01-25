# SK-02 Simulator Integration

## Overview

The SK-02 simulator requires programs in a special text format with one byte per line:

```
<address> <value>
```

Both address and value are in decimal.

## Tools

### `bin2sim` - Binary to Simulator Converter

Standalone Python script that converts `.bin` files to simulator text format.

**Usage:**
```bash
./bin2sim program.bin                  # Creates program.txt
./bin2sim program.bin -o custom.txt    # Specify output
./bin2sim program.bin --org 0x9000     # Different origin
./bin2sim program.bin -v               # Verbose output
```

**Options:**
- `-o, --output FILE` - Output text file (default: input.txt)
- `--org ADDRESS` - Origin address in hex or decimal (default: 0x8000 = 32768)
- `-v, --verbose` - Show progress information
- `-h, --help` - Show help message

**Default Origin:**
The default origin is `0x8000` (32768 decimal), matching the SK-02's ROM start address.

### `sk02-build-sim` - Direct C to Simulator

One-command build from C source to simulator format.

**Usage:**
```bash
./sk02-build-sim program.c              # Creates program.txt
./sk02-build-sim program.c output.txt   # Specify output
```

**What it does:**
1. Compiles C to assembly using `sk02cc`
2. Assembles to binary using `sk02-asm`
3. Converts binary to simulator format using `bin2sim`
4. Cleans up intermediate files (.asm, .bin)

## Example Output Format

Input binary (hello.bin, 7 bytes starting at 0x8000):
```
Byte 0: 0x11 (17)
Byte 1: 0x2A (42)
Byte 2: 0x09 (9)
...
```

Output simulator text (hello.txt):
```
32768 17
32769 42
32770 9
32771 6
32772 128
32773 33
32774 0
```

Each line represents one byte loaded at the specified address.

## Workflow Examples

### Example 1: Build and Simulate

```bash
# Compile C program for simulator
./sk02-build-sim examples/hello.c examples/hello.txt

# Load hello.txt into your SK-02 simulator
# (Simulator-specific commands go here)
```

### Example 2: Test Different Origins

```bash
# Compile normally
./sk02-build-quiet program.c program.bin

# Convert for simulator at different address
./bin2sim program.bin --org 0x9000 -o program_9000.txt
```

### Example 3: Convert Existing Binaries

If you already have assembled binaries:

```bash
# Convert all binaries to simulator format
for bin in examples/*.bin; do
    ./bin2sim "$bin" -v
done
```

### Example 4: Automated Testing

```bash
#!/bin/bash
# Build and prepare for simulator testing

for src in tests/*.c; do
    name=$(basename "$src" .c)
    ./sk02-build-sim "tests/$src" "sim_tests/${name}.txt"
    echo "Prepared $name for simulation"
done
```

## Address Mapping

The SK-02 memory map:

```
$0000-$3FFF (0-16383)     RAM (16KB)
$8000-$FFFF (32768-65535) ROM (32KB)
```

Most programs start at `$8000` (32768), which is the default origin for the assembler and `bin2sim`.

If your program uses a different origin:

```bash
# Assemble with custom origin
uv run sk02-asm program.asm --org 0x9000 -o program.bin

# Convert with matching origin
./bin2sim program.bin --org 0x9000 -o program.txt
```

## File Types Summary

| Extension | Description | Tool |
|-----------|-------------|------|
| `.c` | C source code | `sk02cc` |
| `.asm` | Assembly source | `sk02-asm` |
| `.bin` | Raw binary | `bin2sim` |
| `.txt` | Simulator format | Load in simulator |

## Simulator Text Format Specification

**Format:**
```
address_decimal value_decimal\n
```

**Rules:**
- One byte per line
- Address and value separated by single space
- Both values in base 10 (decimal)
- No leading zeros required
- No comments or headers
- Lines must be in ascending address order (recommended but not always required)

**Valid:**
```
32768 17
32769 42
32770 9
```

**Invalid:**
```
32768 0x11      # No hex values
32768,17        # No commas
0x8000 17       # No hex addresses
32768: 17       # No colons
```

## Integration with Makefiles

```makefile
# Generate simulator files
%.txt: %.bin
\t./bin2sim $< -o $@

# Full C to simulator
%.txt: %.c
\t./sk02-build-sim $< $@

# Build all examples for simulator
sim-examples: $(patsubst %.c,%.txt,$(wildcard examples/*.c))

clean-sim:
\trm -f examples/*.txt tests/*.txt
```

## Troubleshooting

### "Read 0 bytes from file"

The binary file is empty or doesn't exist. Check that assembly succeeded:

```bash
ls -lh program.bin  # Should show file size
```

### "Address range: 32768 to 32768"

Your binary is only 1 byte. This might be correct, or compilation failed partially.

### Simulator doesn't load the file

Check that:
1. File is plain text (not binary)
2. Values are in decimal (not hex)
3. No extra characters or formatting
4. Each line is `<address> <value>` format

Verify format:
```bash
head -5 program.txt
# Should show lines like: 32768 17
```

### Wrong origin address

If your program doesn't execute correctly, you may have the wrong origin:

```bash
# Check what origin the assembler used
grep "ORG" program.asm

# Rebuild with correct origin
uv run sk02-asm program.asm --org 0x8000 -o program.bin
./bin2sim program.bin --org 0x8000 -o program.txt
```

## See Also

- `BUILD_GUIDE.md` - Complete build system documentation
- `docs/compiler-usage.md` - C compiler reference
- `README.md` - Project overview
