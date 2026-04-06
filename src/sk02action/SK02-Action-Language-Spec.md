# SK-02 Action — Language Specification

## Overview

SK-02 Action is a procedural systems programming language derived from Clinton Parker's Action! (OSS, 1983). It retains the core language design — static variable allocation, ALGOL-style structured control flow, and data types mapped directly to 8-bit and 16-bit hardware — while removing all Atari-specific dependencies.

The language is designed as a cross-compiled language. Source code is written on a modern host system, compiled to SK-02 assembly source, and then assembled to a binary ROM image using the existing SK-02 macro assembler.

### Design Principles

- **No recursion.** All variables are statically allocated at compile time. This eliminates stack frame overhead entirely, which is critical on the SK-02's accumulator-centric architecture with no base+offset addressing.
- **Hardware-native types.** The three fundamental types (BYTE, CARD, INT) correspond directly to the SK-02's 8-bit registers and 16-bit register pairs.
- **Transparent compilation.** The programmer should be able to predict what machine code a construct will produce. The language does not hide the machine.
- **Code density over abstraction.** On a ~1 kHz machine with 64 KB of address space, compact output matters more than language elegance.

### Ancestry

The language syntax and semantics are based on Action! 3.6 as documented in the OSS Action! Reference Manual (1983) and released under GPL in 2015. The primary changes from Action! are the removal of the Atari runtime library and I/O system, and the addition of SK-02-specific intrinsics for hardware access.

---

## Lexical Elements

### Character Set

Source files are ASCII text. The language is case-insensitive by default (identifiers `count`, `Count`, and `COUNT` are equivalent). An optional compiler flag enables case sensitivity.

### Identifiers

An identifier begins with a letter (A–Z, a–z) and may contain letters, digits (0–9), and the underscore character (`_`). Maximum length is 255 characters. Identifiers must not be keywords.

### Keywords

The following words are reserved and may not be used as identifiers:

```
AND       DO        FUNC      INTERRUPT OD        RSH       TO
ARRAY     ELSE      IF        LSH       OR        SET       TYPE
BYTE      ELSEIF    INCLUDE   MOD       POINTER   STEP      UNTIL
CARD      EXIT      INT       MODULE    PROC      THEN      WHILE
CHAR      FI        DEFINE    RETURN    XOR
```

### Comments

A semicolon (`;`) begins a comment that extends to the end of the line. Everything after the semicolon is ignored by the compiler.

```
BYTE count  ; this is a comment
; this entire line is a comment
```

### Numeric Constants

Three formats are supported:

- **Decimal:** `42`, `65535`, `-7`
- **Hexadecimal:** Prefixed with `$`. Example: `$FF`, `$D000`, `$4A06`
- **Character:** A single quote followed by a character. Example: `'A`, `'0`, `'z`. The value is the ASCII code of the character.

Negative signs may precede both decimal and hexadecimal constants.

### String Constants

A string constant is zero or more characters enclosed in double quotes. To include a literal double quote within a string, use two consecutive double quotes.

```
"Hello World"
"A ""quoted"" word"
""                    ; empty string
```

Strings are stored in memory as a length byte followed by the character data. The maximum string length is 255 characters (the length byte is a single BYTE with range 0–255).

### Compiler Constants

A compiler constant is evaluated at compile time and may be:

- A numeric constant
- A previously declared identifier (its address is used)
- A pointer reference
- The sum of any two of the above

These are used in variable address placement, SET directives, and array sizing.

---

## Data Types

### Fundamental Types

| Type | Size | Range | Description |
|------|------|-------|-------------|
| BYTE | 1 byte | 0 to 255 | Unsigned 8-bit integer |
| CHAR | 1 byte | 0 to 255 | Alias for BYTE, used for character data |
| CARD | 2 bytes | 0 to 65535 | Unsigned 16-bit integer, stored little-endian |
| INT  | 2 bytes | -32768 to 32767 | Signed 16-bit integer, stored little-endian |

`BYTE` and `CHAR` are interchangeable. The compiler treats them identically.

**Implicit constant typing:** A numeric constant less than 256 is treated as BYTE; otherwise it is CARD. Negative constants are treated as INT.

### Extended Types

Extended types are built on the fundamental types:

- **POINTER** — A 16-bit address pointing to a value of a specified type
- **ARRAY** — A contiguous sequence of values of a specified type, accessed by index
- **TYPE/Record** — A named structure grouping multiple fields at fixed offsets

These are described in detail in their respective sections below.

---

## Variable Declarations

Variables must be declared before use. Declarations may appear immediately after a `MODULE` statement or at the beginning of a `PROC` or `FUNC` body.

### Basic Format

```
<type> <ident> [=<address>] [=[<value>]] {, <ident> [=<address>] [=[<value>]]}
```

- `<type>` is one of `BYTE`, `CHAR`, `CARD`, `INT`
- `=<address>` places the variable at a specific memory address (a compiler constant)
- `=[<value>]` initializes the variable to a value (a numeric constant)

### Examples

```
BYTE top, hat                    ; two BYTE variables
BYTE x=$8000                     ; BYTE at address $8000
INT num=[0]                      ; INT initialized to 0
CARD ctr=[$83D4],                ; three CARDs with initializers
     bignum=[0],
     cat=[3000]
```

A comma after the last variable in a list is an error. Declarations may span multiple lines as long as commas separate the variables.

### Scope

Variables declared after `MODULE` or before any `PROC`/`FUNC` are **global** — visible from their point of declaration to the end of the source file.

Variables declared at the beginning of a `PROC` or `FUNC` body are **local** — visible only within that routine. Since there is no recursion, local variables are assigned fixed memory addresses just like globals. Two routines that never call each other may have their locals overlaid at the same addresses (this is an optional compiler optimization).

---

## Expressions

### Operators

#### Arithmetic Operators

| Operator | Operation | Operand Types |
|----------|-----------|---------------|
| `+` | Addition | BYTE, CARD, INT |
| `-` | Subtraction | BYTE, CARD, INT |
| `*` | Multiplication | BYTE, CARD, INT |
| `/` | Division (integer) | BYTE, CARD, INT |
| `MOD` | Modulo (remainder) | BYTE, CARD, INT |
| `LSH` | Left shift | BYTE, CARD, INT |
| `RSH` | Right shift (logical, zero-fill) | BYTE, CARD, INT |

Multiplication, division, and modulo are implemented as software library routines since the SK-02 has no hardware multiply or divide. They are functional but slow.

`RSH` always performs a logical (unsigned) right shift, filling the vacated high bits with zeros. This matches original Action! behavior. To perform an arithmetic (sign-preserving) right shift on a signed value, the programmer must test and restore the sign bit manually.

#### Bitwise Operators

| Operator | Operation |
|----------|-----------|
| `AND` | Bitwise AND |
| `OR` | Bitwise OR |
| `XOR` | Bitwise exclusive OR |
| `%` | Bitwise NOT (unary, on right operand) |

#### Relational Operators

| Operator | Meaning |
|----------|---------|
| `=` | Equal |
| `<>` | Not equal |
| `<` | Less than |
| `>` | Greater than |
| `<=` | Less than or equal |
| `>=` | Greater than or equal |

Relational operators yield 1 (true) or 0 (false) as a BYTE value.

### Operator Precedence (highest to lowest)

| Precedence | Operators |
|------------|-----------|
| 1 (highest) | `@` (address-of), unary `-`, `%` (bitwise NOT) |
| 2 | `*`, `/`, `MOD`, `LSH`, `RSH` |
| 3 | `+`, `-` |
| 4 | `=`, `<>`, `<`, `>`, `<=`, `>=` |
| 5 | `AND`, `OR`, `XOR` |
| 6 (lowest) | (assignment) |

Parentheses may be used to override precedence: `(a + b) * c`.

### Arithmetic Expressions

Arithmetic expressions combine variables, constants, and operators to produce a value. The type of the result is determined by the widest operand: if either operand is CARD or INT (both 16-bit), the operation is performed at 16-bit width; if both are BYTE, the operation is 8-bit.

**All arithmetic is unsigned.** This matches original Action! behavior. The INT type affects only how values are interpreted by the programmer — at the machine level, CARD and INT are both 16-bit values and the same instructions are used for both. Signed comparison and signed right shift must be handled explicitly by the programmer (e.g., testing the high bit before comparing magnitude).

```
x + 1
(a * b) RSH 2
count MOD 10
```

### Relational Expressions

A relational expression compares two values and produces a BYTE result of 0 or 1.

```
x > 10
count = 0
a + b <> c
```

### Complex Relational Expressions

Relational expressions may be combined with `AND`, `OR`, and `XOR`:

```
(x > 0) AND (x < 100)
(flag = 1) OR (count = 0)
```

---

## Statements

### Assignment Statement

The assignment operator is `=`. The left side must be a variable, array element, pointer dereference, or record field.

**Note:** The `=` symbol serves three roles in the language: assignment in statements, equality comparison in expressions, and address/value specification in declarations. The parser distinguishes these by context — this is inherited from original Action! and is unambiguous given the grammar structure.

```
x = 10
count = count + 1
ptr^ = value
buffer(i) = 'A
```

### Conditional Execution

#### IF Statement

```
IF <condition> THEN
  <statements>
ELSEIF <condition> THEN
  <statements>
ELSE
  <statements>
FI
```

`ELSEIF` and `ELSE` clauses are optional. Multiple `ELSEIF` clauses are permitted.

```
IF x > 100 THEN
  x = 100
ELSEIF x < 0 THEN
  x = 0
FI
```

### Loops

All loops are bracketed by `DO` and `OD`.

#### Unconditional Loop

```
DO
  <statements>
OD
```

This loops forever unless an `EXIT` statement is encountered.

#### WHILE Loop

```
WHILE <condition>
DO
  <statements>
OD
```

The condition is tested before each iteration. The loop body executes zero or more times.

#### UNTIL Loop

```
UNTIL <condition>
DO
  <statements>
OD
```

The condition is tested before each iteration. The loop continues while the condition is false (i.e., it exits when the condition becomes true). Note: despite the name, `UNTIL` tests before the loop body, not after.

#### FOR Loop

```
FOR <ident> = <start> TO <limit> [STEP <increment>]
DO
  <statements>
OD
```

The loop variable is set to `<start>` and incremented by `<increment>` (default 1) after each iteration. The loop exits when the variable exceeds `<limit>`. For negative STEP values, the loop exits when the variable is less than `<limit>`.

**BYTE wraparound warning:** If the loop variable is BYTE and `<limit>` is 255, incrementing past 255 wraps to 0, and the exit condition is never met — the loop runs forever. This is inherited from original Action! behavior. To iterate over the full 0–255 range, use a CARD loop variable or restructure the loop with WHILE/UNTIL and an explicit EXIT.

```
FOR i = 0 TO 9
DO
  buffer(i) = 0
OD

FOR j = 100 TO 0 STEP -1
DO
  ; count down from 100
OD
```

### EXIT Statement

`EXIT` immediately exits the innermost enclosing `DO`/`OD` loop. Execution continues with the statement following the `OD`.

```
DO
  ch = GetKey()
  IF ch = 27 THEN  ; ESC key
    EXIT
  FI
OD
```

### RETURN Statement

`RETURN` exits the current `PROC` or `FUNC`. In a `FUNC`, it must be followed by a parenthesized expression providing the return value (see Functions below).

`RETURN` may appear anywhere in the body of a routine, not only at the end. Early returns are permitted and commonly used in conditional logic. However, every routine must have at least one `RETURN` as its final statement — execution must not fall off the end of a routine.

---

## Procedures and Functions

### Procedures (PROC)

A procedure is a named block of code that performs an action. It does not return a value.

#### Declaration

```
PROC <name>(<param declarations>)
  <local variable declarations>
  <statements>
RETURN
```

Parameter declarations use the same syntax as variable declarations but without initializers or address placement:

```
PROC FillMemory(CARD start, BYTE value, BYTE length)
  CARD ptr
  ptr = start
  WHILE length > 0
  DO
    ptr^ = value
    ptr = ptr + 1
    length = length - 1
  OD
RETURN
```

#### Calling Procedures

A procedure is called by its name followed by parenthesized arguments:

```
FillMemory($4000, 0, 255)
```

### Functions (FUNC)

A function is like a procedure but returns a value. The return type is declared before the function name.

#### Declaration

```
<type> FUNC <name>(<param declarations>)
  <local variable declarations>
  <statements>
RETURN (<expression>)
```

```
BYTE FUNC Max(BYTE a, BYTE b)
  IF a > b THEN
    RETURN (a)
  FI
RETURN (b)
```

#### Calling Functions

Functions are called within expressions. The return value is used as an operand:

```
biggest = Max(x, y)
IF Max(a, b) > threshold THEN ...
```

### Parameters

Parameters are passed by value. Since all storage is static, parameters are simply copied into the routine's fixed parameter locations before the call. The maximum number of parameters is not formally limited but should be kept small for efficiency.

To modify a caller's variable, pass its address using `@` and receive it as a `POINTER`:

```
PROC Increment(BYTE POINTER p)
  p^ = p^ + 1
RETURN

PROC Main()
  BYTE x=[5]
  Increment(@x)   ; x is now 6
RETURN
```

### Program Entry Point

The last `PROC` in the source file is the program entry point. Execution begins there. (There is no requirement to name it `Main`, though it is conventional.)

### No Recursion

A routine may not call itself, directly or indirectly. The compiler allocates fixed addresses for all local variables and parameters. If routine A calls routine B, their storage must not overlap. The compiler builds a call graph and allocates accordingly. Violating this (e.g., through function pointers forming a cycle) produces undefined behavior.

---

## Pointers

### Declaration

A pointer is declared with the `POINTER` keyword following the base type:

```
BYTE POINTER bp
CARD POINTER cp
INT POINTER ip
```

### Address-Of Operator (@)

The `@` operator yields the address of a variable:

```
BYTE x
BYTE POINTER bp
bp = @x
```

### Dereferencing (^)

The `^` operator dereferences a pointer, accessing the value at the pointed-to address:

```
bp^ = 42       ; store 42 at the address in bp
value = bp^    ; load the value at the address in bp
```

### Pointer Arithmetic

Pointers support addition and subtraction with integer offsets. The offset is in units of the base type size (1 for BYTE, 2 for CARD/INT):

```
BYTE POINTER bp
bp = bp + 1     ; advance to next byte
CARD POINTER cp
cp = cp + 1     ; advance by 2 bytes (one CARD)
```

---

## Arrays

### Declaration

An array is declared with the `ARRAY` keyword and a size in parentheses:

```
BYTE ARRAY buffer(256)
CARD ARRAY table(100)
```

The size must be a compiler constant. Arrays are zero-indexed.

An array may also be initialized with data:

```
BYTE ARRAY message = "Hello World"
BYTE ARRAY digits = [0 1 2 3 4 5 6 7 8 9]
```

String initializers store the string's length byte followed by the character data. Bracket initializers list values separated by spaces (not commas). The array size is determined by the number of initializer values. Values must be numeric constants appropriate to the element type.

An array may be placed at a specific address:

```
BYTE ARRAY screen = $8000
```

### Access

Array elements are accessed with parenthesized indices:

```
buffer(0) = 'H
x = table(i)
table(i + 1) = table(i)
```

The index is scaled by the element size. For BYTE arrays, the index is added directly to the base address. For CARD/INT arrays, the index is multiplied by 2 before adding.

### Internal Representation

An array variable holds the base address of the array data. It is effectively a typed pointer. Passing an array to a routine passes the base address.

---

## Records (TYPE)

### Defining a Record Type

A record type is defined with the `TYPE` declaration:

```
TYPE Point = [BYTE x, BYTE y]
TYPE Rect  = [Point topLeft, Point bottomRight]
TYPE Entry = [CARD key, BYTE ARRAY name(16)]
```

Fields are laid out sequentially in memory with no padding.

### Declaring Record Variables

```
Point p1, p2
Rect bounds
```

### Field Access

Record fields are accessed with the dot (`.`) operator:

```
p1.x = 10
p1.y = 20
```

**Note:** Only one level of dot access is supported per expression, matching original Action! behavior. To access nested record fields (e.g., `bounds.topLeft.x`), use an intermediate pointer or variable:

```
; Instead of: bounds.topLeft.x = 0  (NOT supported)
; Use:
Point POINTER pp
pp = @bounds          ; point to start of bounds
pp^.x = 0            ; access topLeft.x (first field)
```

### Records and Pointers

A pointer to a record allows indirect field access:

```
Point POINTER pp
pp = @p1
pp^.x = 10
```

---

## Compiler Directives

### DEFINE

`DEFINE` creates a compile-time text substitution macro:

```
DEFINE SCREEN_WIDTH = "40"
DEFINE LCD_CTRL = "$E000"
DEFINE TRUE = "1"
DEFINE FALSE = "0"
```

Wherever the macro name appears in subsequent source, it is replaced with the substitution text. Macros are not variables — they have no address and no storage.

### INCLUDE

`INCLUDE` inserts the contents of another source file at the current position:

```
INCLUDE "stdlib.act"
INCLUDE "sk02io.act"
```

### SET

`SET` writes a value directly to a memory address at compile time. This is used to initialize memory locations in the output binary:

```
SET $FFFE = entry_point   ; set reset vector
SET 14 = 0                ; initialize a fixed location
```

### MODULE

`MODULE` declares a scope boundary. Global variable declarations may follow a `MODULE` statement. It also resets the compiler's local symbol table, allowing identifier reuse across modules.

```
MODULE

BYTE shared_counter=[0]
CARD buffer_address=[$4000]

PROC Utility()
  ; ...
RETURN

MODULE

PROC Main()
  ; ...
RETURN
```

---

## SK-02 Specific Considerations

### Code Origin and Boot Sequence

The SK-02 begins execution at address `$8000` after reset. The compiler places all generated code and constant data starting at an origin address, which defaults to `$8000`. This can be overridden with the `--origin` compiler flag:

```
sk02ac program.act                    ; output starts at $8000 (default)
sk02ac program.act --origin $4000     ; output starts at $4000
```

The compiler generates the following startup sequence at the origin address, before the program's own code:

1. Initialize stack 0 pointer (return address stack) to its configured page.
2. Initialize stack 1 pointer (data stack) to its configured page.
3. If an `INTERRUPT PROC` is declared, set IVect to its address.
4. Jump to the program entry point (the last `PROC` in the source file).

This startup code is the first thing executed after reset. The programmer does not need to write it — it is emitted automatically.

**Note:** The binary output is a flat ROM image. Bytes are laid out sequentially from the origin address. Code, constant data (string literals, array initializers), and initialized global variables are all placed in the ROM image. Uninitialized variables are allocated addresses in RAM above the end of the ROM image but occupy no space in the ROM image itself. The compiler reports the first free RAM address after compilation so the programmer knows where unallocated memory begins.

### Register Mapping

The compiler maps operations to SK-02 registers as follows:

- **A, B** — Used for all arithmetic. Expression evaluation loads operands into A and B, performs the operation, and leaves the result in A.
- **CD** — Primary pointer register pair. Used for the first (or only) pointer dereference, array access, or indirect load/store in an expression.
- **EF** — Secondary pointer register pair. Used when two simultaneous pointers are needed (e.g., memory copy).
- **GH** — Tertiary pointer register pair. Available as a third address register.
- **AB** — Used as a 16-bit accumulator for CARD/INT arithmetic.

The programmer does not directly control register assignment. The compiler manages this transparently. For cases where direct hardware control is needed, inline assembly or address-placed variables should be used.

### Hardware Access

Variables placed at specific memory addresses provide direct access to memory-mapped hardware such as the LCD:

```
CARD lcd_ctrl = $F000     ; mapped to LCD control address
BYTE shared_flag = $8000  ; a known RAM location shared with external hardware
```

Reading or writing these variables compiles to direct loads from or stores to the specified addresses.

**Note:** The GPIO, X, Y, Out 0, and Out 1 registers are NOT memory-mapped — they are accessed via dedicated CPU opcodes. Use the I/O intrinsics (`GpioRead`, `ReadX`, `Out0Write`, etc.) documented in the Extensions section to access these.

### Multiplication and Division

The SK-02 has no hardware multiply or divide. The operators `*`, `/`, and `MOD` compile to calls into a software math library that must be linked with the program. These routines use shift-and-add/subtract algorithms and are slow (hundreds of instructions per operation at minimum). Use `LSH`/`RSH` for powers of two where possible.

### Code Size

Every conditional branch compiles to a 3-byte absolute jump. The SK-02 has no relative jumps and no inverted conditionals, so an `IF` with an `ELSE` clause typically requires a jump-over-jump pattern (6+ bytes of branch instructions). The compiler should optimize simple cases where possible, but programmers should be aware that deeply nested conditionals produce substantial code.

### Stack Depth

The SK-02 has a 256-byte return address stack (~128 levels of `GOSUB` nesting). Deeply nested procedure calls will exhaust this. There is no way to detect impending overflow — it causes a hard halt. Keep call depth reasonable.

### Data Stack

The SK-02's data stack (Stack 1, used for PUSH/POP of registers) is also 256 bytes within a page. The compiler may use this for saving/restoring registers during expression evaluation and procedure calls. This is managed automatically but imposes a limit on expression complexity and parameter count.

---

## Extensions to Action!

The following features are additions to the original Action! language, introduced to support the SK-02 hardware. These do not exist in Clinton Parker's Action! 3.6.

### Interrupt Handlers (INTERRUPT PROC)

The `INTERRUPT` keyword modifies a `PROC` declaration to mark it as a hardware interrupt handler. An interrupt procedure differs from a normal procedure in three ways:

1. It takes no parameters.
2. The compiler automatically saves and restores all registers that the handler body (and any routines it calls) uses. This is necessary because an interrupt can fire at any point during main program execution, and any registers the handler touches would otherwise corrupt in-progress computations.
3. It compiles to `RETURN_HWI` instead of `RETURN`, which pops the return address from stack 0 and clears the hardware interrupt busy flag.

#### Declaration

```
INTERRUPT PROC <name>()
  <local variable declarations>
  <statements>
RETURN
```

#### Example

```
INTERRUPT PROC OnTimer()
  BYTE val
  val = HwiValue()
  IF val AND 1 THEN
    tick_count = tick_count + 1
  FI
RETURN
```

#### Compiler Behavior

When the compiler encounters `INTERRUPT PROC`, it:

1. Analyzes the handler body and its call graph to determine which registers are modified (A, B, C, D, E, F, G, H).
2. Emits `PUSH_x` instructions for each modified register at the handler entry point.
3. Emits matching `POP_x` instructions (in reverse order) before the `RETURN_HWI`.
4. Emits `RETURN_HWI` instead of `RETURN`.

The register save/restore uses the data stack (Stack 1). Each saved register costs 1 byte. In the worst case (all 8 registers), this consumes 8 bytes per interrupt invocation. The data stack must have sufficient space — if the main program also uses PUSH/POP heavily, stack overflow is possible and will cause a hard halt.

#### Restrictions

- Only one `INTERRUPT PROC` may be declared per program. The SK-02 has a single hardware interrupt vector. Declaring more than one is a compile-time error.
- `INTERRUPT PROC` must take no parameters. A parameter list is a compile-time error.
- `INTERRUPT PROC` cannot be called directly from normal code. It is invoked only by the hardware interrupt mechanism.
- The SK-02's HWI busy flag prevents nested interrupts by default.
- An `INTERRUPT PROC` may call normal procedures and functions, but those routines' register usage is included in the save/restore analysis.

### Interrupt Vector Setup

The compiler automatically generates startup code that sets the hardware interrupt vector (IVect) to the address of the `INTERRUPT PROC` before the program entry point is called. There is no runtime intrinsic for this — the programmer does not need to install the handler manually.

The SK-02 hardware has no interrupt enable/disable mechanism. If an `INTERRUPT PROC` is declared, it will be invoked whenever the hardware triggers an interrupt, from the moment the program starts.

If no `INTERRUPT PROC` is declared, the compiler does not emit any `SET_IV` startup code. The interrupt vector (IVect) will contain whatever value was left in memory. If external hardware triggers an interrupt in this state, behavior is undefined — execution will jump to an arbitrary address. Programs that do not declare an interrupt handler must ensure that no hardware interrupts are triggered, or must set IVect to a safe address manually using the `SET` directive.

### Interrupt Intrinsics

The following built-in routines provide access to the SK-02's interrupt hardware. They compile to one or two native instructions each — there is no library call overhead.

#### BYTE FUNC HwiValue()

Returns the contents of the hardware interrupt value register. This tells the handler what triggered the interrupt. Only meaningful inside an `INTERRUPT PROC`.

```
BYTE val
val = HwiValue()
```

Compiles to: `HWI>A`.

#### TriggerHwi()

Software-triggers a hardware interrupt. This sets the HWI flag and value register as if an external interrupt had occurred. Primarily useful for testing interrupt handlers during development.

```
TriggerHwi()
```

Compiles to: `TRG_HWI`.

### Software Interrupt Intrinsics

The SK-02 also has a software interrupt flag — a simple boolean that can be set externally (e.g., by GPIO/keypad input) and polled by the program. This is not a vectored interrupt; the program must explicitly test the flag.

#### BYTE FUNC InterruptFlag()

Returns 1 if the software interrupt flag is set, 0 otherwise. This compiles to a test-and-branch sequence using `JMP_INTER`.

```
IF InterruptFlag() THEN
  ; handle the software interrupt
  ClearInterrupt()
FI
```

#### ClearInterrupt()

Clears the software interrupt flag.

```
ClearInterrupt()
```

Compiles to: `CLEAR_INTER`.

### Typical Interrupt Setup Pattern

A complete program using hardware interrupts follows this pattern:

```
BYTE tick_count=[0]

INTERRUPT PROC OnTimer()
  BYTE val
  val = HwiValue()
  tick_count = tick_count + 1
RETURN

PROC Main()
  ; interrupt vector is set automatically by compiler startup code —
  ; OnTimer is already installed when Main begins executing

  ; main program loop
  DO
    ; do work...
    ; tick_count is updated asynchronously by OnTimer
    IF tick_count >= 60 THEN
      tick_count = 0
      ; one second has elapsed
    FI
  OD
RETURN
```

The compiler generates startup code that sets IVect to the address of `OnTimer` before calling `Main`. It also ensures that `OnTimer` saves and restores any registers it uses, so the main loop's register state is preserved across interrupts.

### Volatile Variables

Variables that are modified by an interrupt handler and read by the main program (or vice versa) must be treated as **volatile** — the compiler must not cache their values in registers across statements. In the example above, `tick_count` is modified by `OnTimer` and read by `Main`.

The compiler identifies volatile variables automatically: any global variable that is referenced by both an `INTERRUPT PROC` (or a routine reachable from one) and by non-interrupt code is treated as volatile. For each access, the compiler emits a load from or store to the variable's RAM address rather than relying on a register that might hold a stale value.

### I/O Intrinsics

The SK-02's I/O registers are not memory-mapped — they are accessed via dedicated opcodes. Normal load/store instructions cannot reach them. The following intrinsics expose these registers to the language. Each compiles to a single native instruction.

#### GPIO

The GPIO port is an 8-bit bidirectional I/O register.

```
GpioWrite(value)            ; write BYTE value to GPIO port
```

Compiles to: load value into A, then `A>GPIO`.

```
BYTE FUNC GpioRead()        ; read GPIO port
```

Compiles to: `GPIO>A`.

#### External Inputs (X and Y)

Two 8-bit read-only input registers. These are set externally by hardware (DIP switches, keypad, ADC, etc.) and cannot be written by the program.

```
BYTE FUNC ReadX()            ; read the X input register
```

Compiles to: `X>A`.

```
BYTE FUNC ReadY()            ; read the Y input register
```

Compiles to: `Y>A`.

#### Output Displays (Out 0 and Out 1)

Two 8-bit output registers, typically driving 7-segment displays or LED indicators.

```
Out0Write(value)             ; write BYTE value to output display 0
```

Compiles to: load value into A, then `A>OUT_0`.

```
Out1Write(value)             ; write BYTE value to output display 1
```

Compiles to: load value into A, then `A>OUT_1`.

```
OutWrite(lo, hi)             ; write both output displays simultaneously
```

Compiles to: load lo into A and hi into B, then `AB>OUT`.

#### I/O Example

```
PROC ReadAndEcho()
  BYTE input, switches

  input = ReadX()
  switches = GpioRead()

  Out0Write(input)
  Out1Write(switches)

  IF input AND $80 THEN
    GpioWrite($FF)         ; signal high on GPIO
  ELSE
    GpioWrite($00)
  FI
RETURN
```

---

## Standard Library

The standard library is a set of routines provided as Action! source files that are compiled and linked with the user's program via `INCLUDE`. These are not compiler intrinsics — they are ordinary `PROC` and `FUNC` definitions that use the I/O intrinsics and memory-mapped hardware internally.

The library source files are part of the SK-02 Action distribution and are included in the program with:

```
INCLUDE "sk02lcd.act"
INCLUDE "sk02str.act"
```

### LCD Library (sk02lcd.act)

The SK-02 has a 2×20 character LCD display accessed through two consecutive memory-mapped RAM addresses. The base address is configurable (set via the LCD register at startup). The LCD library provides a clean interface to this hardware.

The LCD protocol works as follows: writing to the base address controls the display (value 1 resets and clears; setting bit 7 sets the cursor position in the remaining 7 bits). Writing to base+1 pushes a character at the current cursor position and advances the cursor. Line 0 uses positions 0–19, line 1 uses positions 64–83 (bit 6 selects the line).

#### Configuration

The LCD base address must be set before using any LCD routines. This is typically done once at program startup:

```
LcdInit(base_addr)
```

Sets the internal LCD base address pointer and clears the display. `base_addr` is a CARD specifying the two consecutive RAM addresses used by the LCD hardware.

#### Display Control

```
LcdClear()
```

Clears both lines of the display and resets the cursor to position 0.

```
LcdSetPos(BYTE pos)
```

Sets the cursor position. Positions 0–19 address line 0, positions 64–83 address line 1. The value is written with bit 7 set to the LCD control address.

#### Text Output

```
LcdPutChar(BYTE ch)
```

Writes a single character at the current cursor position and advances the cursor.

```
LcdPrint(BYTE ARRAY str)
```

Writes a string to the display starting at the current cursor position. The string's length byte determines how many characters are written. Characters beyond the end of the current line are silently discarded.

```
LcdPrintAt(BYTE ARRAY str, BYTE line, BYTE col)
```

Sets the cursor to the specified line (0 or 1) and column (0–19), then writes the string. This is a convenience routine combining `LcdSetPos` and `LcdPrint`.

#### Number Output

```
LcdPrintByte(BYTE val)
```

Prints a BYTE value as a decimal number (1–3 digits, no leading zeros) at the current cursor position.

```
LcdPrintCard(CARD val)
```

Prints a CARD value as a decimal number (1–5 digits, no leading zeros) at the current cursor position.

```
LcdPrintInt(INT val)
```

Prints an INT value as a signed decimal number (optional minus sign, 1–5 digits) at the current cursor position.

```
LcdPrintHex(BYTE val)
```

Prints a BYTE value as a two-digit hexadecimal number at the current cursor position.

```
LcdPrintHexCard(CARD val)
```

Prints a CARD value as a four-digit hexadecimal number at the current cursor position.

#### LCD Example

```
INCLUDE "sk02lcd.act"

PROC Main()
  BYTE temp
  CARD counter=[0]

  LcdInit($F000)           ; LCD mapped at $F000–$F001

  LcdPrintAt("SK-02 Ready", 0, 0)
  LcdPrintAt("Count:", 1, 0)

  DO
    counter = counter + 1
    LcdSetPos(64 + 7)      ; line 1, column 7
    LcdPrintCard(counter)

    temp = ReadX()
    IF temp > 0 THEN
      LcdSetPos(14)        ; line 0, column 14
      LcdPrintHex(temp)
    FI
  OD
RETURN
```

### String Library (sk02str.act)

Basic string manipulation routines. Strings in SK-02 Action are BYTE ARRAYs with a length byte at index 0, followed by character data starting at index 1.

```
BYTE FUNC StrLen(BYTE ARRAY s)
```

Returns the length of string `s` (the value at `s(0)`).

```
StrCopy(BYTE ARRAY dest, BYTE ARRAY src)
```

Copies string `src` into `dest`, including the length byte. The destination array must be large enough to hold the source string.

```
StrAppend(BYTE ARRAY dest, BYTE ARRAY src)
```

Appends string `src` to the end of `dest`. Updates the length byte of `dest`. The destination array must have sufficient space.

```
BYTE FUNC StrEqual(BYTE ARRAY a, BYTE ARRAY b)
```

Returns 1 if strings `a` and `b` are identical (same length and same characters), 0 otherwise.

```
ByteToStr(BYTE val, BYTE ARRAY dest)
```

Converts a BYTE value to its decimal string representation and stores it in `dest`.

```
CardToStr(CARD val, BYTE ARRAY dest)
```

Converts a CARD value to its decimal string representation and stores it in `dest`.

```
IntToStr(INT val, BYTE ARRAY dest)
```

Converts an INT value to its signed decimal string representation and stores it in `dest`.

### Memory Library (sk02mem.act)

Block memory operations. These use the SK-02's auto-increment load/store instructions (LO_A_CD++, ST_A_EF++, etc.) for efficient sequential access.

```
MemSet(CARD addr, BYTE value, CARD length)
```

Fills `length` bytes starting at `addr` with `value`.

```
MemCopy(CARD dest, CARD src, CARD length)
```

Copies `length` bytes from `src` to `dest`. Source and destination must not overlap.

```
BYTE FUNC MemEqual(CARD addr1, CARD addr2, CARD length)
```

Compares `length` bytes at `addr1` and `addr2`. Returns 1 if all bytes are identical, 0 otherwise.

---

## Grammar (EBNF)

```ebnf
program        = { module_body } .

module_body    = [ "MODULE" ] { declaration } { routine } .

declaration    = type_decl | define_decl | set_decl | include_decl .

type_decl      = fundtype var_list
               | fundtype "POINTER" var_list
               | fundtype "ARRAY" var_list
               | "TYPE" ident "=" "[" field_list "]" .

var_list       = var_item { "," var_item } .

var_item       = ident [ "=" address ] [ "=" "[" const_expr "]" ]
               | ident "(" const_expr ")"                            (* array with size *)
               | ident "=" string_const                              (* array with string initializer *)
               | ident "=" "[" number { number } "]" .               (* array with space-separated values *)

field_list     = field { "," field } .
field          = fundtype ident
               | fundtype "ARRAY" ident "(" const_expr ")" .

fundtype       = "BYTE" | "CHAR" | "CARD" | "INT" .

routine        = proc_decl | func_decl | interrupt_decl .

proc_decl      = "PROC" ident "(" [ param_list ] ")"
                 { local_decl }
                 stmt_list                               (* may contain early RETURN statements *)
                 "RETURN" .

interrupt_decl = "INTERRUPT" "PROC" ident "(" ")"       (* no parameters allowed;                    *)
                 { local_decl }                          (* only one per program — single HW vector;  *)
                 stmt_list                               (* compiler auto-inserts register save/restore *)
                 "RETURN" .                              (* compiler emits RETURN_HWI instead of RETURN *)

func_decl      = fundtype "FUNC" ident "(" [ param_list ] ")"
                 { local_decl }
                 stmt_list                               (* may contain early RETURN(expr) statements *)
                 "RETURN" "(" expr ")" .                 (* final RETURN with value is mandatory      *)

param_list     = param { "," param } .
param          = fundtype ident
               | fundtype "POINTER" ident
               | fundtype "ARRAY" ident .

local_decl     = fundtype var_list .

stmt_list      = { statement } .

statement      = assign_stmt
               | call_stmt
               | if_stmt
               | do_stmt
               | for_stmt
               | while_stmt
               | until_stmt
               | exit_stmt
               | return_stmt .

assign_stmt    = lvalue "=" expr .

lvalue         = ident
               | ident "(" expr ")"          (* array element — symbol table: ident is ARRAY *)
               | ident "^"                   (* pointer deref *)
               | ident "." ident             (* record field *)
               | ident "^" "." ident .       (* pointer-to-record field *)

                                (* NOTE: ident "(" ... ")" is syntactically ambiguous —  *)
                                (* it matches both call_stmt and array access in lvalue/ *)
                                (* primary. The parser resolves this by consulting the   *)
                                (* symbol table: if ident was declared as PROC or FUNC,  *)
                                (* this is a call. If declared as ARRAY, this is an       *)
                                (* element access. This is an intentional design choice   *)
                                (* inherited from Action! — it keeps the grammar simple   *)
                                (* at the cost of requiring a single-pass parser that     *)
                                (* tracks declarations.                                   *)

call_stmt      = ident "(" [ expr { "," expr } ] ")" .  (* symbol table: ident is PROC/FUNC *)

if_stmt        = "IF" expr "THEN"
                 stmt_list
                 { "ELSEIF" expr "THEN" stmt_list }
                 [ "ELSE" stmt_list ]
                 "FI" .

do_stmt        = "DO" stmt_list "OD" .

for_stmt       = "FOR" ident "=" expr "TO" expr [ "STEP" expr ]
                 "DO" stmt_list "OD" .

while_stmt     = "WHILE" expr "DO" stmt_list "OD" .

until_stmt     = "UNTIL" expr "DO" stmt_list "OD" .

exit_stmt      = "EXIT" .

return_stmt    = "RETURN" [ "(" expr ")" ] .

expr           = and_expr { ("OR" | "XOR") and_expr } .

and_expr       = rel_expr { "AND" rel_expr } .

rel_expr       = add_expr { rel_op add_expr } .
rel_op         = "=" | "<>" | "<" | ">" | "<=" | ">=" .

add_expr       = mul_expr { ("+" | "-") mul_expr } .

mul_expr       = unary_expr { ("*" | "/" | "MOD" | "LSH" | "RSH") unary_expr } .

unary_expr     = [ "-" | "@" | "%" ] primary .

primary        = number
               | char_const
               | string_const
               | ident                        (* simple variable *)
               | ident "(" expr ")"           (* symbol table: ARRAY -> element access,  *)
                                              (*                FUNC  -> function call    *)
               | ident "^"                    (* pointer deref *)
               | ident "." ident              (* record field *)
               | "(" expr ")" .

number         = decimal_number | hex_number .
decimal_number = [ "-" ] digit { digit } .
hex_number     = "$" hex_digit { hex_digit } .
char_const     = "'" character .
string_const   = '"' { character } '"' .
const_expr     = number | ident | const_expr "+" const_expr .

define_decl    = "DEFINE" ident "=" string_const .
set_decl       = "SET" const_expr "=" const_expr .
include_decl   = "INCLUDE" string_const .

(* ------------------------------------------------------------------ *)
(* COMPILER INTRINSICS                                                 *)
(*                                                                     *)
(* The following identifiers are predeclared by the compiler.          *)
(* They use normal call syntax but compile to inline instructions,     *)
(* not subroutine calls. They cannot be redefined.                     *)
(*                                                                     *)
(* NOTE: The interrupt vector (IVect) is set automatically by          *)
(* compiler-generated startup code if an INTERRUPT PROC exists.        *)
(* There is no runtime intrinsic for this.                             *)
(*                                                                     *)
(* --- Interrupt ---                                                   *)
(* Procedures:                                                         *)
(*   TriggerHwi()      — software-trigger hardware interrupt (TRG_HWI) *)
(*   ClearInterrupt()  — clear software interrupt flag (CLEAR_INTER)   *)
(* Functions:                                                          *)
(*   HwiValue()        — HWI value register (HWI>A)                    *)
(*   InterruptFlag()   — 1 if software interrupt set, else 0           *)
(*                                                                     *)
(* --- GPIO ---                                                        *)
(* Procedures:                                                         *)
(*   GpioWrite(val)    — write BYTE to GPIO port (A>GPIO)              *)
(* Functions:                                                          *)
(*   GpioRead()        — read GPIO port (GPIO>A)                       *)
(*                                                                     *)
(* --- External Inputs ---                                             *)
(* Functions:                                                          *)
(*   ReadX()           — read X input register (X>A)                   *)
(*   ReadY()           — read Y input register (Y>A)                   *)
(*                                                                     *)
(* --- Output Displays ---                                             *)
(* Procedures:                                                         *)
(*   Out0Write(val)    — write BYTE to output 0 (A>OUT_0)              *)
(*   Out1Write(val)    — write BYTE to output 1 (A>OUT_1)              *)
(*   OutWrite(lo, hi)  — write both outputs (AB>OUT)                   *)
(* ------------------------------------------------------------------ *)
```

---

## Example Program

```
; SK-02 Action example: read inputs and display on LCD

INCLUDE "sk02lcd.act"
INCLUDE "sk02str.act"

BYTE FUNC Clamp(BYTE val, BYTE max)
  IF val > max THEN
    RETURN (max)
  FI
RETURN (val)

PROC Main()
  BYTE x, y, sum
  BYTE ARRAY buf(8)

  LcdInit($F000)
  LcdPrintAt("SK-02 Action!", 0, 0)

  DO
    x = ReadX()
    y = ReadY()
    sum = Clamp(x + y, 255)

    Out0Write(sum)

    LcdSetPos(64)            ; line 1, column 0
    LcdPrint("X=")
    LcdPrintByte(x)
    LcdPrint(" Y=")
    LcdPrintByte(y)
    LcdPrint(" S=")
    LcdPrintByte(sum)
  OD
RETURN
```

---

## Differences from Original Action!

| Feature | Original Action! | SK-02 Action |
|---------|-----------------|--------------|
| Target CPU | MOS 6502 | SK-02 (custom 8/16-bit) |
| Compilation model | Self-hosted on Atari | Cross-compiled on host PC |
| Output format | 6502 machine code in RAM | SK-02 assembly source text |
| Runtime library | Atari CIO-based (Print, Input, Graphics, etc.) | SK-02-specific (LCD, GPIO, X/Y inputs) |
| I/O model | Atari IOCB channels (Open, Close, Put, Get) | Direct memory-mapped hardware access |
| Editor/Monitor/Debugger | Built into cartridge ROM | Not applicable (host-side tooling) |
| SET directive | Pokes Atari hardware during compilation | Sets bytes in output binary image |
| String I/O | PrintE, InputS, etc. from cartridge library | User-provided library routines |
| Floating point | Not supported (but Atari ROM routines available) | Not supported |
| Interrupt handlers | Not supported | `INTERRUPT PROC` with automatic register save/restore |
| Interrupt intrinsics | Not applicable | HwiValue, TriggerHwi, InterruptFlag, ClearInterrupt; IVect set automatically by compiler |
| Volatile detection | Not applicable | Automatic for variables shared between interrupt and main code |
| Core language syntax | Unchanged | Unchanged (plus INTERRUPT keyword) |
| Data types | Unchanged | Unchanged |
| Control flow | Unchanged | Unchanged |
| Pointers, arrays, records | Unchanged | Unchanged |
| Static allocation model | Unchanged | Unchanged |
| No recursion | Unchanged | Unchanged |
