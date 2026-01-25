# SK-02 C Subset Feasibility Analysis

## Executive Summary

Implementing a C subset for the SK-02 is **feasible but with significant constraints**. The architecture supports enough features for a useful "Tiny C" dialect, but lacks the stack architecture needed for full C semantics.

**Verdict: Implement "SK02-C" - a restricted C subset optimized for this architecture.**

---

## SK-02 Architecture Analysis

### Hardware Resources

| Resource | Capability | C Mapping |
|----------|-----------|-----------|
| **Registers** | A, B, C, D, E, F, G, H (8-bit each) | 4× char or 4× int (as pairs) |
| **Register Pairs** | AB, CD, EF, GH (16-bit) | Pointers, int variables |
| **Address Space** | 64KB (16-bit addressing) | Far pointers unnecessary |
| **Stack** | Hardware-managed (PUSH/POP, GOSUB/RETURN) | Return addresses only |
| **Indirect Addressing** | Via CD, EF, GH pairs | Pointer dereferencing |
| **Auto-increment** | LO_A_CD++, ST_A_CD++, etc. | Array iteration |

### Strengths for C Implementation

1. **16-bit pointer arithmetic** - AB+CD, AB-CD, AB++, etc.
2. **Indirect memory access** - LOAD_A_CD, STORE_A_CD, etc.
3. **Auto-increment addressing** - Efficient array/string operations
4. **Bitwise operations** - AND, OR, XOR, NOT, NAND, NOR, shifts
5. **Signed arithmetic** - S_A>> (arithmetic shift with sign extension)
6. **Subroutine calls** - GOSUB/RETURN

### Critical Limitations

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| **No software stack pointer** | Cannot implement stack frames | Static allocation, no recursion |
| **No indexed addressing** | `array[i]` requires pointer setup | Use register pair as base |
| **No multiply/divide** | Must implement in software | Runtime library |
| **Limited conditionals** | Only ZERO, OVERFLOW, POSITIVE, EVEN | Combine multiple tests |
| **8 registers only** | Register pressure | Spill to static memory |

---

## Proposed C Subset: "SK02-C"

### Supported Data Types

```c
// Native types
char        // 8-bit, maps to A or B register
int         // 16-bit, maps to register pair (AB, CD, EF, GH)
char*       // 16-bit pointer
int*        // 16-bit pointer

// Type qualifiers
register    // Hint to keep in register
static      // All locals are static anyway
const       // ROM placement
```

### NOT Supported
- `long`, `float`, `double` (no hardware support)
- `unsigned` modifier (treat all as signed for simplicity)
- `struct`, `union` (would require complex memory layout)
- `enum` (could add later, trivial)

### Supported Operators

```c
// Arithmetic (int and char)
+  -  *  /  %      // * / % via runtime library

// Bitwise
&  |  ^  ~  <<  >>

// Comparison
==  !=  <  >  <=  >=

// Logical
&&  ||  !

// Assignment
=  +=  -=  &=  |=  ^=  <<=  >>=

// Pointer
*ptr  &var  ptr[index]  ptr++  ptr--
```

### Control Flow

```c
// Fully supported
if (cond) { } else { }
while (cond) { }
for (init; cond; step) { }
break;
continue;
return value;

// NOT supported
switch/case    // Would require jump tables
goto           // Could add, low priority
```

### Functions

```c
// Supported: up to 4 parameters, 1 return value
int add(int a, int b) {
    return a + b;
}

// Parameters passed in registers:
// - 2 char params: A, B
// - 2 int params: AB, CD
// - 4 char params: A, B, C, D (C,D clobbered)
// - Return value in A (char) or AB (int)

// NOT supported
// - Recursion (no stack frames)
// - Variadic functions (printf-style)
// - Function pointers (could add, complex)
```

### Variables

```c
// Global variables - stored in RAM
int counter;
char buffer[64];

// Local variables - actually static!
void foo() {
    int x;      // Warning: static storage, NOT re-entrant
    char y;
}

// Register variables - compiler hint
void bar() {
    register int i;  // Try to keep in EF or GH
}
```

### Pointers and Arrays

```c
// Pointer declaration and use
char* ptr;
*ptr = 42;
ptr++;

// Array access (desugars to pointer arithmetic)
char arr[10];
arr[i] = x;     // Compiles to: *(arr + i) = x

// String literals - stored in ROM
char* msg = "Hello";
```

---

## Memory Model

```
$0000-$3FFF  RAM (16KB)
  $0000-$00FF  Zero page (fast access) - globals, static locals
  $0100-$01FF  Runtime library workspace
  $0200-$3FFF  General RAM - arrays, buffers

$8000-$FFFF  ROM (32KB)
  $8000-$xxxx  Code
  $xxxx-$FEFF  String literals, const data
  $FF00-$FFFF  Interrupt vectors
```

### Calling Convention

```
Arguments:
  1st char/int  -> A (char) or AB (int)
  2nd char/int  -> B (char) or CD (int)
  3rd-4th char  -> C, D (if not used by int args)

Return value:
  char          -> A
  int           -> AB

Callee-saved:
  EF, GH (must be preserved across calls)

Caller-saved:
  A, B, C, D (may be clobbered)
```

---

## Example: What Code Would Look Like

### SK02-C Source
```c
// LED blinker with delay
char delay_count;

void delay(char loops) {
    while (loops > 0) {
        loops--;
    }
}

void main() {
    while (1) {
        output(0xFF);   // LEDs on
        delay(100);
        output(0x00);   // LEDs off
        delay(100);
    }
}
```

### Generated Assembly
```asm
; void delay(char loops)  - loops in A
_delay:
.loop:
        A_ZERO          ; test A == 0
        JMP_ZERO .done
        A--
        JMP .loop
.done:
        RETURN

; void main()
_main:
.loop:
        SET_A #$FF
        A>GPIO          ; output(0xFF)
        SET_A #100
        GOSUB _delay

        SET_A #$00
        A>GPIO          ; output(0x00)
        SET_A #100
        GOSUB _delay

        JMP .loop
```

---

## Implementation Complexity

### Compiler Phases

| Phase | Complexity | Notes |
|-------|-----------|-------|
| Lexer | Low | Standard tokenization |
| Parser | Medium | Subset grammar is simple |
| Type Checker | Low | Only char/int/pointer |
| IR Generation | Medium | SSA or simple 3-address |
| Register Allocation | Medium | 4 pairs, graph coloring |
| Code Generation | Medium | Pattern matching to opcodes |
| Optimizer | Optional | Peephole, constant folding |

### Runtime Library Requirements

```c
// Must implement in assembly:
int __mul8(char a, char b);     // 8x8 -> 16 multiply
int __mul16(int a, int b);      // 16x16 -> 16 multiply
int __div16(int a, int b);      // 16/16 -> 16 divide
int __mod16(int a, int b);      // 16%16 -> 16 modulo
void __memcpy(char* dst, char* src, int len);
void __memset(char* dst, char val, int len);
```

---

## Comparison with Similar Projects

| System | Word Size | Stack | C Subset |
|--------|----------|-------|----------|
| **SK-02** | 8/16-bit | Hardware only | SK02-C (proposed) |
| CC65 (6502) | 8-bit | Software | Nearly full C |
| SDCC (Z80) | 8-bit | Software | Nearly full C |
| Small-C | 16-bit | Software | Subset |

The SK-02 is more constrained than 6502/Z80 due to lacking a software stack pointer, making it closer to Small-C's approach but with even more restrictions.

---

## Recommendation

### Phase 1: Minimal Viable Compiler
- Types: `char`, `int`, `char*`, `int*`
- Operators: arithmetic, bitwise, comparison
- Control: `if`, `while`, `for`, `return`
- Functions: non-recursive, max 2 int params
- Variables: global only

### Phase 2: Usable Compiler
- Local variables (static storage, with warnings)
- Arrays and string literals
- More operators (`++`, `--`, compound assignment)
- Functions: up to 4 params

### Phase 3: Full SK02-C
- Register hints
- Inline assembly blocks
- Basic optimizations
- Const/ROM placement

---

## Conclusion

A C subset for SK-02 is **feasible and practical** with these constraints:
1. No recursion (static locals)
2. Limited function parameters (register passing)
3. No structs/unions
4. No floating point

The resulting "SK02-C" would be similar to early 1970s C compilers, sufficient for:
- Control applications
- Simple games
- I/O drivers
- Educational projects

**Estimated effort: 2-4 weeks for Phase 1, using Python with the existing assembler as backend.**
