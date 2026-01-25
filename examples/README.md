# SK02-C Examples

This directory contains example C programs demonstrating the SK02-C compiler features.

## Examples

### `hello.c` - LED Blinker
Simple LED blinker with delay function.

**Features demonstrated:**
- Global variables
- Functions with parameters
- While loops
- Function calls

**Build:**
```bash
./sk02-build hello.c
./sk02-build-sim hello.c hello.txt  # For simulator
```

### `simple_test.c` - Minimal Test
Simplest possible program.

**Features demonstrated:**
- Local variables
- Basic assignment

### `arithmetic.c` - Math Operations
Arithmetic and bitwise operations.

**Features demonstrated:**
- Int and char types
- Arithmetic operators (+, -)
- Bitwise operators (&, |, ^, ~, <<, >>)
- Function return values

### `loops.c` - Control Flow
For and while loops with counters.

**Features demonstrated:**
- For loops
- While loops
- Loop increment/decrement
- Nested loops
- Global and local variables

### `conditionals.c` - If/Else
Conditional statements and comparisons.

**Features demonstrated:**
- If/else statements
- Comparison operators (>, <, ==, !=)
- Nested conditionals
- Functions returning values

## Building Examples

### Build All Examples (Binary)
```bash
for f in examples/*.c; do
    ./sk02-build-quiet "$f"
done
```

### Build All Examples (Simulator)
```bash
for f in examples/*.c; do
    ./sk02-build-sim "$f" "${f%.c}.txt"
done
```

### Build Single Example
```bash
# Binary
./sk02-build hello.c

# Simulator
./sk02-build-sim hello.c hello.txt
```

## Expected Output Sizes

| Example | Binary Size | Description |
|---------|-------------|-------------|
| simple_test.c | 7 bytes | Minimal program |
| hello.c | 70 bytes | Delay loop blinker |
| arithmetic.c | 182 bytes | Math operations |
| loops.c | 233 bytes | Loop examples |
| conditionals.c | 257 bytes | If/else examples |

## Learning Path

Recommended order for learning SK02-C:

1. **simple_test.c** - Understand basic structure
2. **hello.c** - Learn functions and loops
3. **arithmetic.c** - Explore operators
4. **conditionals.c** - Master if/else
5. **loops.c** - Combine everything

## Modifying Examples

All examples can be freely modified. To test your changes:

```bash
# Edit the file
nano examples/hello.c

# Rebuild
./sk02-build examples/hello.c

# Or for simulator
./sk02-build-sim examples/hello.c examples/hello.txt
```

## Common Patterns

### Delay Function
```c
void delay(char loops) {
    while (loops > 0) {
        loops--;
    }
}
```

### Counter Pattern
```c
int counter;

void increment() {
    counter++;
}
```

### Comparison Pattern
```c
char max(char a, char b) {
    if (a > b) {
        return a;
    }
    return b;
}
```

## Limitations to Remember

- **No recursion** - Functions cannot call themselves
- **Static locals** - Local variables persist between calls
- **Limited parameters** - Max 2 int or 4 char parameters
- **No structs** - Only basic types (char, int, pointers)
- **No arrays yet** - Coming in Phase 2

See `docs/compiler-usage.md` for complete details.
