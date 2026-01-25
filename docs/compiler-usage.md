# SK02-C Compiler Usage Guide

## Overview

SK02-C is a C subset compiler for the SK-02 8-bit computer. It compiles a restricted C dialect to SK-02 assembly language, which can then be assembled using the `sk02-asm` assembler.

## Installation

```bash
uv sync
```

## Basic Usage

### Build Scripts (Recommended)

The easiest way to build is using the provided shell scripts:

```bash
# Interactive mode - asks to keep .asm file
./sk02-build program.c

# Specify output binary
./sk02-build program.c custom.bin

# Quiet mode - no prompts, auto-cleanup
./sk02-build-quiet program.c program.bin
```

### Manual Compilation

```bash
# Compile to assembly (output: program.asm)
uv run sk02cc program.c

# Specify output file
uv run sk02cc program.c -o output.asm

# Compile and assemble in one step
uv run sk02cc program.c && uv run sk02-asm program.asm -o program.bin
```

### Python API

```python
from sk02cc import compile_string, compile_file

# Compile from string
source = """
void main() {
    char x = 42;
}
"""
assembly = compile_string(source)

# Compile from file
compile_file("program.c", "program.asm")
```

## Supported C Features

### Data Types

```c
char    // 8-bit signed integer
int     // 16-bit signed integer
char*   // 16-bit pointer to char
int*    // 16-bit pointer to int
```

### Operators

**Arithmetic**: `+`, `-`, `*`, `/`, `%`
*Note: `*`, `/`, `%` require runtime library (not yet implemented)*

**Bitwise**: `&`, `|`, `^`, `~`, `<<`, `>>`

**Comparison**: `==`, `!=`, `<`, `>`, `<=`, `>=`

**Logical**: `&&`, `||`, `!`

**Assignment**: `=`, `+=`, `-=`, `&=`, `|=`, `^=`

**Increment/Decrement**: `++`, `--` (prefix and postfix)

**Pointer**: `*ptr`, `&var`

### Control Flow

```c
// Conditional
if (condition) {
    // ...
} else {
    // ...
}

// Loops
while (condition) {
    // ...
}

for (init; condition; increment) {
    // ...
}

// Loop control
break;
continue;

// Function return
return value;
```

### Functions

```c
// Function declaration and definition
char add(char a, char b) {
    return a + b;
}

// Void function
void setup() {
    // ...
}

// Function call
char result = add(10, 20);
```

**Limitations**:
- Maximum 2 `int` parameters or 4 `char` parameters
- Single return value only
- No recursion (all locals are static)
- No function pointers

### Variables

```c
// Global variables
int counter;
char buffer[64];

// Local variables (actually static!)
void foo() {
    int x = 10;
    char y;
}

// Register hint (optimization request)
void bar() {
    register char i;
    for (i = 0; i < 10; i++) {
        // ...
    }
}
```

**Important**: All local variables use static storage. Functions are **NOT re-entrant**.

## Examples

### Example 1: Simple Counter

```c
// counter.c
int count;

void increment() {
    count++;
}

void main() {
    count = 0;
    increment();
    increment();
    increment();
}
```

Compile and run:
```bash
# Easy way
./sk02-build-quiet counter.c

# Or manually
uv run sk02cc counter.c
uv run sk02-asm counter.asm -o counter.bin
```

### Example 2: LED Blinker

```c
// blink.c
void delay(char loops) {
    while (loops > 0) {
        loops--;
    }
}

void main() {
    while (1) {
        // Assuming GPIO control at address
        char led = 0xFF;
        delay(100);
        led = 0x00;
        delay(100);
    }
}
```

### Example 3: Math Operations

```c
// math.c
int result;

int add(int a, int b) {
    return a + b;
}

char max(char a, char b) {
    if (a > b) {
        return a;
    }
    return b;
}

void main() {
    result = add(100, 200);
    char m = max(42, 17);
}
```

## Common Patterns

### Array Iteration

```c
char buffer[10];
char i;

void fill_buffer() {
    for (i = 0; i < 10; i++) {
        buffer[i] = i * 2;
    }
}
```

### Bit Manipulation

```c
char flags;

void set_bit(char bit) {
    flags = flags | (1 << bit);
}

void clear_bit(char bit) {
    flags = flags & ~(1 << bit);
}

char test_bit(char bit) {
    return (flags & (1 << bit)) != 0;
}
```

### State Machines

```c
char state;

void update_state() {
    if (state == 0) {
        state = 1;
    } else if (state == 1) {
        state = 2;
    } else {
        state = 0;
    }
}
```

## Error Messages

The compiler provides detailed error messages with line and column information:

```
Lexer error at 5:10: Unexpected character: '@'
Parse error at 12:5: Expected SEMICOLON, got IDENTIFIER
Compilation error: Undefined variable: foo
```

## Limitations and Warnings

### Current Limitations

1. **No recursion** - Functions cannot call themselves
2. **Static locals** - All local variables are static (not on stack)
3. **Limited parameters** - Max 2 int or 4 char parameters
4. **No structs/unions** - Only basic types
5. **No arrays as parameters** - Pass pointers instead
6. **No multiply/divide** - Runtime library needed (Phase 2)
7. **No string operations** - Use manual loops
8. **No preprocessor** - No #include, #define, etc.

### Phase 1 vs Future Phases

**Current (Phase 1)**:
- Basic types (char, int, pointers)
- Arithmetic, bitwise, logical operators
- Control flow (if, while, for)
- Functions with limited parameters
- Global variables only

**Phase 2** (Planned):
- Local variables with warnings
- Arrays and array access
- String literals
- Runtime library (multiply, divide, memcpy)
- Compound assignment operators

**Phase 3** (Future):
- Register allocation hints
- Inline assembly
- Basic optimizations
- Const/ROM placement

## Tips and Best Practices

1. **Keep functions small** - Limited register space
2. **Use char when possible** - Faster than int
3. **Minimize parameters** - Max 2 ints or 4 chars
4. **Avoid deep nesting** - Register pressure
5. **Use bitwise ops** - Very efficient on SK-02
6. **Comment your code** - Compiler strips comments anyway

## See Also

- [C Subset Feasibility Analysis](c-subset-feasibility.md) - Design rationale
- [Calling Convention](calling-convention.md) - How functions work
- [SK-02 Assembly Reference](../README.md) - Target architecture
