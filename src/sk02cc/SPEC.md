# SK02-C Language Specification

A C subset targeting the SK-02, a homebrew 8-bit computer. Full ANSI C is not realistic —
this spec defines what the hardware can support efficiently, with clear tiers for what is
in scope.

---

## Hardware Constraints Summary

The SK-02 has 8 × 8-bit registers (A–H), four 16-bit pairs (AB, CD, EF, GH), three flags
(zero, overflow, interrupt), a 256-byte data stack (push/pop only, no indexing), and a
256-byte return stack (GOSUB/RETURN only). ROM starts at `$8000`, RAM below that.

Key limitations that shape this spec:

- **No hardware multiply/divide** — must be software subroutines
- **No stack frames** — data stack is push/pop only; no random access, no frame pointer
- **No indexed addressing** — array access requires computing address into CD/EF/GH
- **ALU results only in A** — all arithmetic/logic output lands in A (or AB for 16-bit)
- **Only A and B can directly access memory** — other registers go via A or B
- **Unsigned-first ALU** — signed comparisons require sign-bit checks (extra instructions)
- **CMP semantics:** `overflow = (A - B) < 0` means overflow set when A < B (unsigned)

---

## Types

| SK02-C type  | C alias       | Size    | Notes                                      |
|--------------|---------------|---------|--------------------------------------------|
| `uint8`      | `char`        | 1 byte  | Default unsigned; direct 8-bit ALU support |
| `int8`       | `signed char` | 1 byte  | Signed; comparisons cost 2–4 extra instr.  |
| `uint16`     | `unsigned int`| 2 bytes | Native AB+CD / AB-CD / CMP_16             |
| `int16`      | `int`         | 2 bytes | Signed; comparisons cost extra             |
| `void`       | —             | 0 bytes | Return type only                           |
| `T*`         | —             | 2 bytes | Pointer; stored as uint16 address          |
| `T[N]`       | —             | N×size  | Fixed-size array; no bounds checking       |

`char` is an alias for `uint8`. `int` is an alias for `int16` (matching 8-bit C convention).
Explicit sized types (`uint8`, `uint16`, etc.) are preferred for new code.

**Out of scope:** `long` (32-bit), `float`, `double`, `unsigned long`, `enum`, `struct`,
`union`, `typedef`.

---

## Variables and Storage

### Globals
Allocated in static RAM via `.BYTE`/`.WORD` directives. Accessible from any function.

### Locals
All local variables use **static storage** (no stack frames). This means:
- No recursion — a function's locals are fixed at compile time
- Local label format: `_{funcname}_{varname}`
- Declared anywhere in a function body (C89-style scoping is fine)

### Initializers
- Global: zero-initialized (`.BYTE 0` / `.WORD 0`); non-zero initializers not yet supported
- Local: initializer expression emitted inline at declaration point

---

## Operators

### Fully supported (map directly to hardware or via software subroutine)

| Operator       | Types        | Hardware instruction(s)          |
|----------------|--------------|----------------------------------|
| `+`            | uint8/int8   | `ADD`                            |
| `-` (binary)   | uint8/int8   | `SUB`                            |
| `&`            | uint8/int8   | `AND`                            |
| `\|`           | uint8/int8   | `OR`                             |
| `^`            | uint8/int8   | `XOR`                            |
| `~`            | uint8/int8   | `NOT`                            |
| `<<`           | uint8/int8   | `A<<` (loop for variable shift)  |
| `>>`           | uint8        | `A>>` (logical, loop)            |
| `>>`           | int8         | `S_A>>` (arithmetic, loop)       |
| `+`            | uint16/int16 | `AB+CD`                          |
| `-` (binary)   | uint16/int16 | `AB-CD`                          |
| `<<`           | uint16       | `AB<<` (loop)                    |
| `>>`           | uint16       | `AB>>` (logical, loop)           |
| `>>`           | int16        | `S_AB>>` (arithmetic, loop)      |
| `-` (unary)    | any int      | `NOT` + `A++` (two's complement) |
| `++` / `--`    | any          | `A++`/`A--`/`AB++`/`AB--`        |
| `!`            | any          | `A_ZERO` + conditional           |
| `==` / `!=`    | uint8/int8   | `CMP` + `JMP_ZERO`               |
| `==` / `!=`    | uint16/int16 | `CMP_16` + `JMP_ZERO`            |
| `*`            | uint8        | `GOSUB __rt_mul` (shift-and-add, 16 iterations) |
| `/`            | uint8        | `GOSUB __rt_div` (repeated subtraction)         |
| `%`            | uint8        | `GOSUB __rt_div` + take remainder               |
| `&&` / `\|\|` | any          | short-circuit with conditional jumps            |

### Unsigned comparisons (hardware-native)

| Operator  | After `CMP` (A vs B)         |
|-----------|------------------------------|
| `<`       | overflow set                 |
| `>=`      | overflow clear               |
| `>`       | overflow clear AND zero clear |
| `<=`      | overflow set OR zero set     |

### Signed comparisons (extra instructions — check sign bit first)

`int8`/`int16` comparisons use `JMP_A_POS`/`JMP_B_POS` to handle sign-bit cases before
CMP. Cost: ~4–6 extra instructions per comparison.

### Assignment operators

| Operator                         | Status          |
|----------------------------------|-----------------|
| `=`                              | Supported        |
| `+=`, `-=`, `&=`, `\|=`, `^=`   | Supported        |
| `<<=`, `>>=`                     | Supported        |
| `*=`, `/=`, `%=`                 | Supported (software subroutine) |

### Not supported (Tier 2 or out of scope)

- `?:` (ternary) — out of scope

---

## Control Flow

| Construct      | Status    | Notes                                    |
|----------------|-----------|------------------------------------------|
| `if`/`else`    | Tier 1    |                                          |
| `while`        | Tier 1    |                                          |
| `for`          | Tier 1    |                                          |
| `break`        | Tier 1    |                                          |
| `continue`     | Tier 1    |                                          |
| `return`       | Tier 1    | Value in A (8-bit) or AB (16-bit)        |
| `do`/`while`   | Tier 2    |                                          |
| `switch`/`case`| Tier 2    | Compiled as if/else chain, not jump table|
| `goto`         | Out of scope |                                       |

---

## Functions

### Calling convention

| Position | 8-bit param  | 16-bit param | Notes                          |
|----------|--------------|--------------|--------------------------------|
| Param 1  | Register A   | Register AB  |                                |
| Param 2  | Register B   | Register CD  |                                |
| Param 3+ | Data stack   | Data stack   | Pushed by caller, low byte first|
| Return   | Register A   | Register AB  |                                |

- Callee saves params 1–2 to static storage immediately on entry
- Callee pops params 3+ from stack on entry
- No register save/restore — caller and callee must coordinate; in practice the compiler
  saves live values to stack before calls
- GOSUB/RETURN used for all calls; GOSUB_COMP available for function pointers (Tier 2)

### Constraints
- No recursion (static locals)
- No variadic functions
- Max practical call depth: ~64 nested calls (return stack: 256 bytes, 2 bytes per return
  address; data stack: 256 bytes shared with temporaries and extra params)

---

## Pointers (Tier 2)

- All pointers are `uint16` addresses (2 bytes)
- Dereference `*ptr`: load address into CD/EF/GH, use `LOAD_A_CD` / `LO_AB_CD`
- Address-of `&var`: emit `SET_AB #label`
- Pointer arithmetic: `ptr + n` adds n×sizeof(T) to the 16-bit address via AB+CD
- No `NULL` safety — behaviour on null/invalid pointer is undefined

---

## Arrays (Tier 2)

- Fixed-size only, declared with constant size: `uint8 buf[64]`
- Access `arr[i]`: compute address as base + i×sizeof(T), load into pointer register
- No bounds checking
- Multidimensional arrays: out of scope

---

## Literals

| Form             | Example       | Type     |
|------------------|---------------|----------|
| Decimal integer  | `42`          | int16    |
| Hex integer      | `0xFF`        | uint8/16 |
| Character        | `'A'`, `'\n'` | uint8    |
| String           | `"hello"`     | uint8*   |

String literals are stored in the data section as `.ASCIIZ` and referenced by their
16-bit address.

---

## Preprocessor

Out of scope. No `#include`, `#define`, `#ifdef`. Use the assembler's `.INCLUDE` and
`.MACRO` directives at the assembly level if needed.

---

## Implementation Approach

Use **red/green TDD**: write a failing test first, then implement to pass it. Tests live
in `tests/test_compiler.py` and drive the full pipeline (C source → assembly text, checked
for correct instruction sequences, or end-to-end via the simulator).

### Tier 1 — implement first (core correctness)

1. Fix CMP flag semantics in `codegen.py` (currently inverted for `<`, `>`, `<=`, `>=`)
2. Fix compound assignment operators (`+=` currently behaves as `=`)
3. Fix 16-bit local variable initialization (currently only stores low byte)
4. Fix `result_reg` for binary op RHS (non-literal expressions ignore register target)
5. Add explicit sized types (`uint8`, `int8`, `uint16`, `int16`) alongside `char`/`int`
6. Implement signed comparisons for `int8`/`int16`

### Tier 2 — after Tier 1 is tested and solid

- ~~Software multiply/divide/modulo~~ ✓ Done — `__rt_mul` / `__rt_div` subroutines, emitted only when used
- ~~Logical `&&` / `||`~~ ✓ Done — short-circuit evaluation
- Pointers and address-of (partial)
- Array access
- `do`/`while`, `switch`/`case`
- ~~More than 2 function parameters (stack-passed)~~ ✓ Done — params 3+ pushed right-to-left by caller, popped in order by callee
