# SK02-C Calling Convention

## Register Usage

### 8-bit Registers
- **A, B, C, D** - Caller-saved (scratch registers)
- **E, F, G, H** - Callee-saved (must be preserved)

### 16-bit Register Pairs
- **AB** - First parameter / Return value
- **CD** - Second parameter / Pointer operations
- **EF** - Callee-saved / Local variables
- **GH** - Callee-saved / Local variables

## Function Parameters

### Passing Convention

```c
// char parameters
void func(char a, char b, char c, char d);
// Parameters: A=a, B=b, C=c, D=d

// int parameters
void func(int a, int b);
// Parameters: AB=a, CD=b

// Mixed parameters
void func(int a, char b);
// Parameters: AB=a, C=b (D is scratch)

// Pointer parameters
void func(char* ptr, int count);
// Parameters: AB=ptr, CD=count
```

### Parameter Limits
- Maximum 2 `int` parameters (AB, CD)
- Maximum 4 `char` parameters (A, B, C, D)
- Mixed: 1 int + 2 chars maximum

### More than 2/4 Parameters
If more parameters are needed, use global variables or structures (Phase 3).

## Return Values

```c
char func();    // Return in A
int func();     // Return in AB
char* func();   // Return pointer in AB
```

Only single return values supported. No structure returns.

## Callee Responsibilities

Functions must:
1. Preserve EF and GH if used
2. Can freely use A, B, C, D
3. Return value in A (char) or AB (int)

Example function prologue/epilogue:

```asm
_myfunc:
    ; Prologue - save callee-saved registers if needed
    PUSH_E
    PUSH_F
    PUSH_G
    PUSH_H

    ; Function body...

    ; Epilogue - restore callee-saved registers
    POP_H
    POP_G
    POP_F
    POP_E
    RETURN
```

## Call Sequence

```c
int result = add(5, 10);
```

Generates:

```asm
    SET_AB #5       ; First parameter
    SET_CD #10      ; Second parameter
    GOSUB _add      ; Call function
    ; Result is in AB
    STORE_AB result ; Store return value
```

## Static Local Variables

Since there's no stack frame, all local variables are actually static:

```c
void counter() {
    int count;  // Actually static storage
    count++;
}
```

Generates:

```asm
_counter:
    ; Load static variable
    LOAD_AB _counter.count
    AB++
    ; Store back
    STORE_AB _counter.count
    RETURN

_counter.count:
    .WORD 0
```

**Warning**: Functions with static locals are NOT re-entrant or thread-safe.

## Memory Layout for Function Data

```
$0000-$00FF  Global variables
$0100-$01FF  Static local variables (function.varname)
$0200-$xxxx  Arrays and buffers
```

## Examples

### Simple Function

```c
char add(char a, char b) {
    return a + b;
}
```

```asm
_add:               ; a in A, b in B
    ADD             ; A = A + B
    RETURN          ; Return A
```

### Function with Local Variable

```c
int multiply(char a, char b) {
    int result;
    result = a * b;
    return result;
}
```

```asm
_multiply:          ; a in A, b in B
    PUSH_E          ; Save callee-saved
    PUSH_F

    GOSUB __mul8    ; Call runtime multiply (A*B -> AB)
    STORE_AB _multiply.result
    LOAD_AB _multiply.result

    POP_F
    POP_E
    RETURN

_multiply.result:
    .WORD 0
```

### Function Preserving Registers

```c
void process(int* ptr, int count) {
    // Uses EF as loop counter
}
```

```asm
_process:           ; ptr in AB, count in CD
    PUSH_E          ; Save EF
    PUSH_F

    ; AB = ptr, CD = count
    AB>EF           ; Save ptr in EF

.loop:
    CD_ZERO
    JMP_ZERO .done

    ; Process using EF as pointer
    LOAD_A_EF
    ; ... process byte ...

    EF++
    CD--
    JMP .loop

.done:
    POP_F
    POP_E
    RETURN
```
