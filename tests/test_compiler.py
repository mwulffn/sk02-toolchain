"""Tests for the SK02-C compiler.

Each test class targets a known bug. Tests are written red-first: they describe
the correct behaviour and will fail until the bug is fixed.

Two helpers are provided:
- asm_lines(source): compile → list of stripped, non-comment assembly lines
- run_c(source, A, B): compile → assemble → simulate; returns CPU after execution
"""

import pytest
from sk02cc.compiler import compile_string
from sk02_asm.assembler import Assembler
from simulator.cpu import CPU
from simulator.memory import Memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def asm_lines(source: str) -> list[str]:
    """Compile C source and return stripped, non-empty, non-comment lines."""
    output = compile_string(source)
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.strip().startswith(";")
    ]


def run_c(source: str, *, A: int = 0, B: int = 0, max_instructions: int = 10000) -> CPU:
    """Compile C, assemble, run in simulator, return CPU state.

    Sets up a HALT instruction at $7FFE so RETURN from the first function
    stops execution cleanly. Initial register values A and B can be set to
    simulate passing arguments to the first function.
    """
    asm_source = compile_string(source)

    assembler = Assembler(asm_source, 0x8000)
    output, errors = assembler.assemble()
    assert not errors, f"Assembly errors: {errors}"

    memory = Memory()
    for addr, byte in output.data.items():
        memory.write_byte(addr, byte)

    # Place HALT at $7FFE so RETURN lands there and stops execution
    HALT_OPCODE = 127
    memory.write_byte(0x7FFE, HALT_OPCODE)

    cpu = CPU(memory)
    cpu.A = A & 0xFF
    cpu.B = B & 0xFF
    cpu.push_return(0x7FFE)

    cpu.run(max_instructions)
    return cpu


# ===========================================================================
# BUG 1: CMP flag semantics inverted
#
# The simulator: overflow = (A - B) < 0, so overflow is SET when A < B.
#   A <  B  → overflow set,   zero clear
#   A == B  → overflow clear, zero set
#   A >  B  → overflow clear, zero clear
#
# The codegen docstring says the opposite, so <, >, <=, >= all produce
# wrong results. Only == and != work (they only check the zero flag).
# ===========================================================================

class TestCmpSemantics:
    """CMP-based comparisons must return correct results at runtime."""

    # --- less-than ---

    def test_less_than_true(self):
        """2 < 5 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a < b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 1, f"2 < 5 should be 1, got {cpu.A}"

    def test_less_than_false(self):
        """5 < 2 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a < b) return 1; return 0; }", A=5, B=2)
        assert cpu.A == 0, f"5 < 2 should be 0, got {cpu.A}"

    def test_less_than_equal_values(self):
        """3 < 3 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a < b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 0, f"3 < 3 should be 0, got {cpu.A}"

    # --- greater-than ---

    def test_greater_than_true(self):
        """5 > 2 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a > b) return 1; return 0; }", A=5, B=2)
        assert cpu.A == 1, f"5 > 2 should be 1, got {cpu.A}"

    def test_greater_than_false(self):
        """2 > 5 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a > b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 0, f"2 > 5 should be 0, got {cpu.A}"

    def test_greater_than_equal_values(self):
        """3 > 3 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a > b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 0, f"3 > 3 should be 0, got {cpu.A}"

    # --- less-than-or-equal ---

    def test_lte_true_less(self):
        """2 <= 5 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a <= b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 1, f"2 <= 5 should be 1, got {cpu.A}"

    def test_lte_true_equal(self):
        """3 <= 3 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a <= b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 1, f"3 <= 3 should be 1, got {cpu.A}"

    def test_lte_false(self):
        """5 <= 2 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a <= b) return 1; return 0; }", A=5, B=2)
        assert cpu.A == 0, f"5 <= 2 should be 0, got {cpu.A}"

    # --- greater-than-or-equal ---

    def test_gte_true_greater(self):
        """5 >= 2 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a >= b) return 1; return 0; }", A=5, B=2)
        assert cpu.A == 1, f"5 >= 2 should be 1, got {cpu.A}"

    def test_gte_true_equal(self):
        """3 >= 3 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a >= b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 1, f"3 >= 3 should be 1, got {cpu.A}"

    def test_gte_false(self):
        """2 >= 5 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a >= b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 0, f"2 >= 5 should be 0, got {cpu.A}"

    # --- equal / not-equal: must stay correct after the fix ---

    def test_equal_true(self):
        """3 == 3 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a == b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 1, f"3 == 3 should be 1, got {cpu.A}"

    def test_equal_false(self):
        """2 == 5 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a == b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 0, f"2 == 5 should be 0, got {cpu.A}"

    def test_not_equal_true(self):
        """2 != 5 must return 1."""
        cpu = run_c("char f(char a, char b) { if (a != b) return 1; return 0; }", A=2, B=5)
        assert cpu.A == 1, f"2 != 5 should be 1, got {cpu.A}"

    def test_not_equal_false(self):
        """3 != 3 must return 0."""
        cpu = run_c("char f(char a, char b) { if (a != b) return 1; return 0; }", A=3, B=3)
        assert cpu.A == 0, f"3 != 3 should be 0, got {cpu.A}"


# ===========================================================================
# BUG 2: Compound assignment operators silently act as plain =
#
# generate_assignment ignores expr.op entirely. x += 5 compiles as x = 5.
# ===========================================================================

class TestCompoundAssignment:
    """Compound assignments must read-modify-write, not just write."""

    def test_plus_assign_emits_add(self):
        """x += 5 must emit an ADD instruction."""
        lines = asm_lines("void f() { char x; x += 5; }")
        assert "ADD" in lines, "x += 5 must emit ADD"

    def test_plus_assign_loads_variable_first(self):
        """x += 5 must load x before storing — not just store 5."""
        lines = asm_lines("void f() { char x; x += 5; }")
        store_indices = [i for i, l in enumerate(lines) if "STORE_A _f_x" in l]
        load_indices = [i for i, l in enumerate(lines) if "LOAD_A _f_x" in l]
        assert load_indices, "x += 5 must load x"
        assert store_indices, "x += 5 must store x"
        assert load_indices[-1] < store_indices[-1], (
            "LOAD_A must precede the final STORE_A for x += 5"
        )

    def test_minus_assign_emits_sub(self):
        """x -= 3 must emit a SUB instruction."""
        lines = asm_lines("void f() { char x; x -= 3; }")
        assert "SUB" in lines, "x -= 3 must emit SUB"

    def test_and_assign_emits_and(self):
        """x &= 15 must emit AND."""
        lines = asm_lines("void f() { char x; x &= 15; }")
        assert "AND" in lines, "x &= 15 must emit AND"

    def test_or_assign_emits_or(self):
        """x |= 128 must emit OR."""
        lines = asm_lines("void f() { char x; x |= 128; }")
        assert "OR" in lines, "x |= 128 must emit OR"

    def test_xor_assign_emits_xor(self):
        """x ^= 255 must emit XOR."""
        lines = asm_lines("void f() { char x; x ^= 255; }")
        assert "XOR" in lines, "x ^= 255 must emit XOR"

    def test_plus_assign_runtime(self):
        """x = 3; x += 5 must produce 8, not 5."""
        cpu = run_c("""
            char f() {
                char x;
                x = 3;
                x += 5;
                return x;
            }
        """)
        assert cpu.A == 8, f"x=3; x+=5 should return 8, got {cpu.A}"

    def test_minus_assign_runtime(self):
        """x = 10; x -= 3 must produce 7."""
        cpu = run_c("""
            char f() {
                char x;
                x = 10;
                x -= 3;
                return x;
            }
        """)
        assert cpu.A == 7, f"x=10; x-=3 should return 7, got {cpu.A}"


# ===========================================================================
# BUG 3: 16-bit local variable initializer only stores the low byte
#
# VariableDeclaration handling always emits STORE_A (8-bit) even for int.
# Should use SET_AB + SET_CD + ST_AB_CD for 16-bit locals.
# ===========================================================================

class TestInt16LocalInit:
    """int local variable initializers must store both bytes."""

    def test_int_local_init_uses_16bit_store(self):
        """int x = 1000 must emit ST_AB_CD, not just STORE_A."""
        lines = asm_lines("void f() { int x = 1000; }")
        assert "ST_AB_CD" in lines, "int local init must use ST_AB_CD (16-bit store)"

    def test_int_local_init_sets_cd_pointer(self):
        """int x = 1000 must load address of x into CD before ST_AB_CD."""
        lines = asm_lines("void f() { int x = 1000; }")
        cd_lines = [l for l in lines if l.startswith("SET_CD")]
        assert any("_f_x" in l for l in cd_lines), (
            "int local init must SET_CD #_f_x before ST_AB_CD"
        )

    def test_int_local_zero_init_uses_16bit_store(self):
        """int x = 0 must still use 16-bit store path."""
        lines = asm_lines("void f() { int x = 0; }")
        assert "ST_AB_CD" in lines, "int x = 0 must use ST_AB_CD"

    def test_int_local_init_runtime(self):
        """int x = 1000; return x must produce 1000 in AB (low byte in A = 0xE8)."""
        cpu = run_c("""
            int f() {
                int x = 1000;
                return x;
            }
        """)
        # 1000 = 0x03E8, little-endian: A=0xE8, B=0x03
        assert cpu.A == 0xE8, f"Low byte of 1000 (0xE8) should be in A, got {cpu.A:#x}"
        assert cpu.B == 0x03, f"High byte of 1000 (0x03) should be in B, got {cpu.B:#x}"


# ===========================================================================
# BUG 4: result_reg ignored for non-literal RHS in binary operations
#
# generate_expression(..., "B") is called for the RHS of a binary op, but
# Identifier/BinaryOp/FunctionCall all ignore result_reg and put their result
# in A. The fix: after computing RHS into A, emit A>B, then POP_A.
# ===========================================================================

class TestBinaryOpRhsRegister:
    """Binary ops with variable RHS must yield the correct result."""

    def test_add_two_variables_emits_a_to_b(self):
        """a + b (both variables): must emit A>B to move RHS before POP_A+ADD."""
        lines = asm_lines("""
            char f(char a, char b) { return a + b; }
        """)
        add_idx = lines.index("ADD")
        pop_idx = next(i for i in range(add_idx - 1, -1, -1) if lines[i] == "POP_A")
        pre_pop = lines[:pop_idx]
        assert "A>B" in pre_pop, (
            "RHS variable must be moved to B (A>B) before POP_A restores LHS"
        )

    def test_sub_two_variables_emits_a_to_b(self):
        """a - b: same pattern."""
        lines = asm_lines("""
            char f(char a, char b) { return a - b; }
        """)
        sub_idx = lines.index("SUB")
        pop_idx = next(i for i in range(sub_idx - 1, -1, -1) if lines[i] == "POP_A")
        pre_pop = lines[:pop_idx]
        assert "A>B" in pre_pop, (
            "RHS variable must be moved to B (A>B) before POP_A restores LHS"
        )

    def test_add_two_variables_runtime(self):
        """f(3, 4) must return 7."""
        cpu = run_c("char f(char a, char b) { return a + b; }", A=3, B=4)
        assert cpu.A == 7, f"3 + 4 should return 7, got {cpu.A}"

    def test_sub_two_variables_runtime(self):
        """f(10, 3) must return 7."""
        cpu = run_c("char f(char a, char b) { return a - b; }", A=10, B=3)
        assert cpu.A == 7, f"10 - 3 should return 7, got {cpu.A}"

    def test_literal_rhs_still_uses_set_b(self):
        """a + 1 with literal RHS should still use SET_B (existing correct path)."""
        lines = asm_lines("char f(char a) { return a + 1; }")
        assert "SET_B #1" in lines, "Literal RHS should use SET_B directly"

    def test_literal_rhs_runtime(self):
        """f(6) must return 7 for a + 1."""
        cpu = run_c("char f(char a) { return a + 1; }", A=6)
        assert cpu.A == 7, f"6 + 1 should return 7, got {cpu.A}"
