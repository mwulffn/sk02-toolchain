# SK-02 Action! Compiler — Progress

## Status: Core language features complete + ARRAY initializers + I/O intrinsics + 16-bit arithmetic + SET directive + string literals in expressions

657 tests passing. Full pipeline working end-to-end (Action! source → assembly → assembler → simulator).

## Pipeline

```
Source → Lexer → Parser → TypeChecker → ConstantFolder → CallGraph → CodeGenerator → [Optimizer] → Assembly
```

The optimizer slot is reserved but not yet implemented. It will be an assembly-level pass after codegen.

## What's Working

### Lexer (`tokens.py`, `lexer.py`)
- All 30+ keywords, case-insensitive (identifiers normalized to lowercase)
- Decimal numbers, hex (`$FF`), character constants (`'A`), strings (`"..."` with `""` escaping)
- All operators: `+ - * / = <> < > <= >= @ ^ %`, parens, brackets, comma, dot
- Semicolon comments (to end of line)
- Line/column tracking on all tokens

### Parser (`ast_nodes.py`, `parser.py`)
- Variable declarations: `BYTE x`, `CARD a, b`, `INT num=[0]`, `BYTE x=$8000`
- PROC and FUNC declarations with parameters and local variables
- Full expression precedence (6 levels): OR/XOR → AND → relational → add/sub → mul/div/mod/shift → unary → primary
- The `=` ambiguity: assignment at statement level, equality in expression context
- Statements: assignment, proc call, IF/ELSEIF/ELSE/FI, WHILE/DO/OD, DO/OD, UNTIL/DO/OD, FOR/TO/STEP/DO/OD, EXIT, RETURN
- Function calls in expressions
- `BYTE POINTER bp`, `CARD POINTER cp`, `INT POINTER ip` declarations
- `bp^` dereference as expression and as lvalue (`bp^ = 42`)
- `@x` address-of unary operator
- `BYTE ARRAY buf(256)`, `CARD ARRAY tbl(100)` declarations
- `BYTE ARRAY msg = "Hello World"` string initializer (length byte + char bytes)
- `BYTE ARRAY digits = [0 1 2 3 4]` bracket initializer (space-separated constants)
- `buf(i)` array element access as expression and as lvalue — disambiguated from function calls via a tracked set of declared array names

### Type Checker (`symbol_table.py`, `type_checker.py`)
- Two-scope symbol table (global + one function-local)
- Type widening: BYTE op CARD → CARD, BYTE op INT → INT, INT op CARD → INT
- Relational operators always produce BYTE
- Unary minus produces INT
- Checks: undeclared variables/functions, wrong argument count
- Function call return type resolution
- `PointerType`: size=2; `@x` produces `PointerType(x.type)`; `ptr^` produces `ptr.type.base_type`
- `ArrayType`: size=`elem_size * count`; `arr(i)` produces `arr.type.base_type`

### Constant Folding (`const_fold.py`)
- Folds all arithmetic, bitwise, relational, and shift operations on constants
- Respects 8-bit (BYTE) and 16-bit (CARD/INT) overflow masking
- Preserves signed values for INT type
- Nested folding: `(2 + 3) * 4` → `20`

### Call Graph (`call_graph.py`)
- Builds directed caller→callee graph from AST
- Direct and transitive recursion detection (compile error)
- `can_overlap(a, b)` query for future local variable overlay optimization

### Code Generation (`emitter.py`, `codegen.py`)
- Startup sequence: `.ORG`, `GOSUB _entry`, `HALT`
- 8-bit arithmetic via A/B registers: `LOAD_A`, `SET_A`, `STORE_A`, `ADD`, `SUB`, `AND`, `OR`, `XOR`, `NOT`
- 16-bit arithmetic via AB/CD register pairs: `SET_AB`, `SET_CD`, `LO_AB_CD`, `ST_AB_CD`, `AB+CD`, `AB-CD`
- Software multiply (`__rt_mul`, shift-and-add) and divide/modulo (`__rt_div`, repeated subtraction) — emitted only when used
- Comparisons: `CMP`/`CMP_16` + `JMP_ZERO`/`JMP_OVER` patterns for all 6 relational operators
- IF/ELSEIF/ELSE/FI with conditional jumps
- WHILE/DO/OD, DO/OD, UNTIL/DO/OD, FOR/TO/STEP/DO/OD loops — 8-bit and 16-bit loop variables
- FOR with negative STEP (counts down, reversed exit condition)
- EXIT (break from innermost loop)
- Calling convention: param 1 in A/AB, param 2 in B/CD, params 3+ on data stack
- Callee-side param saves to static storage
- FUNC return values in A (8-bit) or AB (16-bit)
- Data section: `.BYTE`/`.WORD` for storage, `.EQU` for address-placed variables, initialized values for string/bracket array initializers
- Shift left/right via loop (no hardware barrel shifter)
- POINTER: `@x` → `SET_AB #_x`; `ptr^` read via `AB>CD`/`LOAD_A_CD`; `ptr^ = val` write via GH parking
- ARRAY: element access via `base + index * elem_size`; storage as `.BYTE`/`.WORD` sequences

### I/O Intrinsics (`type_checker.py`, `codegen.py`, `call_graph.py`)
- All 11 SK-02 hardware intrinsics predeclared in symbol table at `TypeChecker.__init__`
- Intrinsics compile to inline instructions — no `GOSUB` overhead
- `GpioRead()` → `GPIO>A`, `GpioWrite(val)` → `A>GPIO`
- `ReadX()` → `X>A`, `ReadY()` → `Y>A`
- `Out0Write(val)` → `A>OUT_0`, `Out1Write(val)` → `A>OUT_1`, `OutWrite(lo, hi)` → `AB>OUT`
- `HwiValue()` → `HWI>A`, `TriggerHwi()` → `TRG_HWI`
- `ClearInterrupt()` → `CLEAR_INTER`
- `InterruptFlag()` → `SET_A #1` / `JMP_INTER` / `SET_A #0` sequence
- Call graph skips intrinsic names (they are inlined, not real call targets)

### Orchestration (`compiler.py`, `cli.py`, `__init__.py`)
- `compile_string(source)` and `compile_file(input, output)` API
- `sk02ac` CLI with `--origin`, `-o`, `--version` flags
- Entry point registered in `pyproject.toml`

## What's NOT Working / Deferred

### Language Features (in approximate priority order)

1. **TYPE/Records** — `TYPE Point = [BYTE x, BYTE y]`, field access with `.`. Fully deferred.

3. **DEFINE** — Compile-time text substitution macros. Should be a preprocessor pass before lexing.

4. **INCLUDE** — File inclusion. Also a preprocessor pass.

5. ~~**SET**~~ — Done. `SET $FFFE = entry_point` emits `.ORG`/`.WORD` patch at end of assembly output. Target is numeric constant; value is numeric constant or identifier (resolved to assembly label). Assembler's sparse `BinaryWriter` supports non-monotonic `.ORG`.

6. **MODULE** — Scope boundaries for identifier reuse across modules.

7. **INTERRUPT PROC** — `INTERRUPT PROC OnTimer()`. Requires: call graph analysis for register save/restore sets, `PUSH_x`/`POP_x` prologue/epilogue, `RETURN_HWI` instead of `RETURN`, `SET_IV` in startup, volatile variable detection. Blocked on simulator work (see below).

8. ~~**String constants in expressions**~~ — Done. String literal in expression context (`p = "Hello"`, `f("msg")`) allocates an anonymous BYTE ARRAY `_str_N` in the data section (length-prefix layout: `[len, c0, c1, ...]`) and loads its address into AB via `SET_AB #_str_N`. Type is `PointerType(ByteType)`. String dedup is a future optimization. Strings > 255 chars raise a compile error.

9. ~~**I/O Intrinsics**~~ — Done. All 11 intrinsics implemented.

### Simulator Gaps

The following opcodes are currently no-ops in `simulator/opcodes.py` and need to be implemented before the corresponding compiler features can be fully tested end-to-end:

- `SET_IV` / `AB>IV` / `IV>AB` — interrupt vector register
- `HWI>A` — read hardware interrupt value register
- `TRG_HWI` — software-trigger hardware interrupt
- `RETURN_HWI` — return from interrupt handler (pop return stack + clear HWI busy flag)
- Hardware interrupt auto-dispatch — `cpu.run()` currently never fires an interrupt; needs to check a pending flag and jump to IVect between instructions

These are needed together to test `INTERRUPT PROC` end-to-end.

### Code Generation Gaps

10. **Post-emission optimizer** — Reserved pipeline slot. Should do peephole optimization on the generated assembly (redundant load/store elimination, constant propagation at assembly level, dead code removal).

11. **Local variable overlay** — The call graph's `can_overlap()` is implemented but not used. When two routines share no call path, their locals can share the same RAM addresses. Saves RAM on this 64KB machine.

12. **Volatile variable detection** — Globals shared between INTERRUPT PROC and normal code must not be cached in registers. The call graph can identify these once INTERRUPT PROC is implemented.

13. **Signed 16-bit FOR loops crossing zero** — FOR with INT loop variable and negative limit (e.g., `FOR i = 3 TO -2 STEP -1`) requires signed `CMP_16`. Currently only unsigned comparison is used, so negative limits are treated as large positive values.

14. ~~**16-bit multiply/divide**~~ — Done. `__rt_mul` was already a correct 16×16→16 routine (the `pass` in the 16-bit path was accidentally correct). Added `__rt_div_16` (new routine using AB/CD, restoring-subtraction algorithm). Fixed zero-extension bug where BYTE literals assigned to CARD variables left B with garbage (B not zeroed before `ST_AB_CD`). Fixed mixed BYTE/CARD operands in binary expressions. 6 new e2e tests.

## Test Structure

```
tests/
  test_action_lexer.py      — 58 tests (keywords, numbers, strings, operators, comments, errors)
  test_action_parser.py      — 70 tests (declarations, expressions, statements, pointer, array, SET, string literal, errors)
  test_action_types.py       — 50 tests (symbol table, type checker, widening, pointer, array, I/O intrinsics, SET, string literal)
  test_action_constfold.py   — 21 tests (folding, no-fold, overflow)
  test_action_callgraph.py   — 11 tests (construction, recursion, overlap)
  test_action_codegen.py     — 70 tests (structure, vars, assignment, arithmetic, comparisons, control flow, calls, runtime routines, pointer, array, array initializers, negative literal masking, I/O intrinsics, SET directive, string literal)
  test_action_e2e.py         — 62 tests (full pipeline through simulator, including multiply/divide, 16-bit mul/div, 16-bit FOR, negative STEP, pointer, array, array initializers, I/O intrinsics, SET directive, string literal)
```

Helpers follow the same pattern as `test_compiler.py`: `asm_lines()` for codegen checks, `run_action()` for end-to-end simulation.

## Key Design Decisions

- **Case insensitivity**: Lexer normalizes all identifiers to lowercase.
- **Newlines as whitespace**: Keyword-delimited blocks (IF/FI, DO/OD) make newlines redundant for parsing.
- **`=` resolved by context**: Statement-level = is assignment, expression-level = is equality.
- **Entry point**: Last PROC in source file (per spec).
- **Static labels**: `_varname` for globals, `_funcname_varname` for locals/params.
- **Calling convention**: Same as sk02cc (param 1 in A/AB, param 2 in B/CD, 3+ on data stack).

## Spec Reference

Full language spec: `src/sk02action/SK02-Action-Language-Spec.md`
