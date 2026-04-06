"""Tests for the SK02-C compiler.

Each test class targets a known bug. Tests are written red-first: they describe
the correct behaviour and will fail until the bug is fixed.

Two helpers are provided:
- asm_lines(source): compile → list of stripped, non-comment assembly lines
- run_c(source, A, B): compile → assemble → simulate; returns CPU after execution
"""

import pytest

from simulator.cpu import CPU
from simulator.memory import Memory
from sk02_asm.assembler import Assembler
from sk02cc.compiler import compile_string
from sk02cc.type_checker import SemanticError

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

    The compiled binary starts with JMP _main, so main() is always the entry
    point. A HALT at $7FFE is pushed onto the return stack so RETURN from
    main stops execution cleanly. Initial register values A and B can be set
    to simulate passing arguments to main.
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
        cpu = run_c(
            "char main(char a, char b) { if (a < b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 1, f"2 < 5 should be 1, got {cpu.A}"

    def test_less_than_false(self):
        """5 < 2 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a < b) return 1; return 0; }", A=5, B=2
        )
        assert cpu.A == 0, f"5 < 2 should be 0, got {cpu.A}"

    def test_less_than_equal_values(self):
        """3 < 3 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a < b) return 1; return 0; }", A=3, B=3
        )
        assert cpu.A == 0, f"3 < 3 should be 0, got {cpu.A}"

    # --- greater-than ---

    def test_greater_than_true(self):
        """5 > 2 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a > b) return 1; return 0; }", A=5, B=2
        )
        assert cpu.A == 1, f"5 > 2 should be 1, got {cpu.A}"

    def test_greater_than_false(self):
        """2 > 5 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a > b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 0, f"2 > 5 should be 0, got {cpu.A}"

    def test_greater_than_equal_values(self):
        """3 > 3 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a > b) return 1; return 0; }", A=3, B=3
        )
        assert cpu.A == 0, f"3 > 3 should be 0, got {cpu.A}"

    # --- less-than-or-equal ---

    def test_lte_true_less(self):
        """2 <= 5 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a <= b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 1, f"2 <= 5 should be 1, got {cpu.A}"

    def test_lte_true_equal(self):
        """3 <= 3 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a <= b) return 1; return 0; }", A=3, B=3
        )
        assert cpu.A == 1, f"3 <= 3 should be 1, got {cpu.A}"

    def test_lte_false(self):
        """5 <= 2 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a <= b) return 1; return 0; }", A=5, B=2
        )
        assert cpu.A == 0, f"5 <= 2 should be 0, got {cpu.A}"

    # --- greater-than-or-equal ---

    def test_gte_true_greater(self):
        """5 >= 2 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a >= b) return 1; return 0; }", A=5, B=2
        )
        assert cpu.A == 1, f"5 >= 2 should be 1, got {cpu.A}"

    def test_gte_true_equal(self):
        """3 >= 3 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a >= b) return 1; return 0; }", A=3, B=3
        )
        assert cpu.A == 1, f"3 >= 3 should be 1, got {cpu.A}"

    def test_gte_false(self):
        """2 >= 5 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a >= b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 0, f"2 >= 5 should be 0, got {cpu.A}"

    # --- equal / not-equal: must stay correct after the fix ---

    def test_equal_true(self):
        """3 == 3 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a == b) return 1; return 0; }", A=3, B=3
        )
        assert cpu.A == 1, f"3 == 3 should be 1, got {cpu.A}"

    def test_equal_false(self):
        """2 == 5 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a == b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 0, f"2 == 5 should be 0, got {cpu.A}"

    def test_not_equal_true(self):
        """2 != 5 must return 1."""
        cpu = run_c(
            "char main(char a, char b) { if (a != b) return 1; return 0; }", A=2, B=5
        )
        assert cpu.A == 1, f"2 != 5 should be 1, got {cpu.A}"

    def test_not_equal_false(self):
        """3 != 3 must return 0."""
        cpu = run_c(
            "char main(char a, char b) { if (a != b) return 1; return 0; }", A=3, B=3
        )
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
        lines = asm_lines("void main() { char x; x += 5; }")
        assert "ADD" in lines, "x += 5 must emit ADD"

    def test_plus_assign_loads_variable_first(self):
        """x += 5 must load x before storing — not just store 5."""
        lines = asm_lines("void main() { char x; x += 5; }")
        store_indices = [i for i, l in enumerate(lines) if "STORE_A _main_x" in l]
        load_indices = [i for i, l in enumerate(lines) if "LOAD_A _main_x" in l]
        assert load_indices, "x += 5 must load x"
        assert store_indices, "x += 5 must store x"
        assert load_indices[-1] < store_indices[-1], (
            "LOAD_A must precede the final STORE_A for x += 5"
        )

    def test_minus_assign_emits_sub(self):
        """x -= 3 must emit a SUB instruction."""
        lines = asm_lines("void main() { char x; x -= 3; }")
        assert "SUB" in lines, "x -= 3 must emit SUB"

    def test_and_assign_emits_and(self):
        """x &= 15 must emit AND."""
        lines = asm_lines("void main() { char x; x &= 15; }")
        assert "AND" in lines, "x &= 15 must emit AND"

    def test_or_assign_emits_or(self):
        """x |= 128 must emit OR."""
        lines = asm_lines("void main() { char x; x |= 128; }")
        assert "OR" in lines, "x |= 128 must emit OR"

    def test_xor_assign_emits_xor(self):
        """x ^= 255 must emit XOR."""
        lines = asm_lines("void main() { char x; x ^= 255; }")
        assert "XOR" in lines, "x ^= 255 must emit XOR"

    def test_plus_assign_runtime(self):
        """x = 3; x += 5 must produce 8, not 5."""
        cpu = run_c("""
            char main() {
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
            char main() {
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
        lines = asm_lines("void main() { int x = 1000; }")
        assert "ST_AB_CD" in lines, "int local init must use ST_AB_CD (16-bit store)"

    def test_int_local_init_sets_cd_pointer(self):
        """int x = 1000 must load address of x into CD before ST_AB_CD."""
        lines = asm_lines("void main() { int x = 1000; }")
        cd_lines = [l for l in lines if l.startswith("SET_CD")]
        assert any("_main_x" in l for l in cd_lines), (
            "int local init must SET_CD #_main_x before ST_AB_CD"
        )

    def test_int_local_zero_init_uses_16bit_store(self):
        """int x = 0 must still use 16-bit store path."""
        lines = asm_lines("void main() { int x = 0; }")
        assert "ST_AB_CD" in lines, "int x = 0 must use ST_AB_CD"

    def test_int_local_init_runtime(self):
        """int x = 1000; return x must produce 1000 in AB (low byte in A = 0xE8)."""
        cpu = run_c("""
            int main() {
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
            char main(char a, char b) { return a + b; }
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
            char main(char a, char b) { return a - b; }
        """)
        sub_idx = lines.index("SUB")
        pop_idx = next(i for i in range(sub_idx - 1, -1, -1) if lines[i] == "POP_A")
        pre_pop = lines[:pop_idx]
        assert "A>B" in pre_pop, (
            "RHS variable must be moved to B (A>B) before POP_A restores LHS"
        )

    def test_add_two_variables_runtime(self):
        """f(3, 4) must return 7."""
        cpu = run_c("char main(char a, char b) { return a + b; }", A=3, B=4)
        assert cpu.A == 7, f"3 + 4 should return 7, got {cpu.A}"

    def test_sub_two_variables_runtime(self):
        """f(10, 3) must return 7."""
        cpu = run_c("char main(char a, char b) { return a - b; }", A=10, B=3)
        assert cpu.A == 7, f"10 - 3 should return 7, got {cpu.A}"

    def test_literal_rhs_still_uses_set_b(self):
        """a + 1 with literal RHS should still use SET_B (existing correct path)."""
        lines = asm_lines("char main(char a) { return a + 1; }")
        assert "SET_B #1" in lines, "Literal RHS should use SET_B directly"

    def test_literal_rhs_runtime(self):
        """f(6) must return 7 for a + 1."""
        cpu = run_c("char main(char a) { return a + 1; }", A=6)
        assert cpu.A == 7, f"6 + 1 should return 7, got {cpu.A}"


# ===========================================================================
# BUG 5: Missing explicit sized types (uint8, int8, uint16, int16)
#
# These types are not in the keyword list. They parse as IDENTIFIER tokens,
# causing ParseError. After the fix they must behave exactly like their
# aliases: uint8 ≡ char (1 byte, unsigned), int8 ≡ signed char (1 byte,
# signed), uint16 ≡ unsigned int (2 bytes), int16 ≡ int (2 bytes, signed).
# ===========================================================================


class TestSizedTypes:
    """uint8, int8, uint16, int16 must parse and generate correct code."""

    def test_uint8_variable(self):
        """uint8 x = 42 must compile and return 42."""
        cpu = run_c("char main() { uint8 x = 42; return x; }")
        assert cpu.A == 42, f"uint8 x=42 should return 42, got {cpu.A}"

    def test_int8_variable(self):
        """int8 x = -1 must compile and return 255 (two's complement 8-bit)."""
        cpu = run_c("char main() { int8 x = -1; return x; }")
        assert cpu.A == 255, f"int8 x=-1 should return 255, got {cpu.A}"

    def test_uint16_variable(self):
        """uint16 x = 1000 must compile and return 1000 in AB."""
        cpu = run_c("int main() { uint16 x = 1000; return x; }")
        assert cpu.A == 0xE8, f"Low byte of 1000 (0xE8) expected, got {cpu.A:#x}"
        assert cpu.B == 0x03, f"High byte of 1000 (0x03) expected, got {cpu.B:#x}"

    def test_int16_variable(self):
        """int16 x = 300 must compile and return 300 in AB."""
        # 300 = 0x012C: A=0x2C, B=0x01
        cpu = run_c("int main() { int16 x = 300; return x; }")
        assert cpu.A == 0x2C, f"Low byte of 300 (0x2C) expected, got {cpu.A:#x}"
        assert cpu.B == 0x01, f"High byte of 300 (0x01) expected, got {cpu.B:#x}"

    def test_uint8_function_param(self):
        """uint8 function parameter must be passed and returned correctly."""
        cpu = run_c("uint8 main(uint8 a) { return a; }", A=99)
        assert cpu.A == 99, f"uint8 param should pass 99 through, got {cpu.A}"

    def test_int16_function_param(self):
        """int16 function parameter (AB) must be passed and returned correctly."""
        # Pass 1000: A=0xE8, B=0x03
        cpu = run_c("int16 main(int16 a) { return a; }", A=0xE8, B=0x03)
        assert cpu.A == 0xE8, f"int16 param A=0xE8 expected, got {cpu.A:#x}"
        assert cpu.B == 0x03, f"int16 param B=0x03 expected, got {cpu.B:#x}"

    def test_uint8_arithmetic(self):
        """uint8 a = 10; uint8 b = 3; return a + b must return 13."""
        cpu = run_c("""
            char main() {
                uint8 a = 10;
                uint8 b = 3;
                return a + b;
            }
        """)
        assert cpu.A == 13, f"uint8 10+3 should return 13, got {cpu.A}"

    def test_int8_alias_for_char_size(self):
        """int8 variable must use 1-byte STORE_A, not 2-byte ST_AB_CD."""
        lines = asm_lines("void main() { int8 x = 5; }")
        assert "STORE_A _main_x" in lines, "int8 must use 1-byte STORE_A"
        assert "ST_AB_CD" not in lines, "int8 must not use 2-byte ST_AB_CD"


# ===========================================================================
# BUG 6: Signed comparisons not implemented for int8/int16/int
#
# All comparisons currently use unsigned CMP. For signed types, when the
# operands have different signs, unsigned CMP gives wrong results:
#   -1 < 1 would test 255 < 1 → false (wrong: signed -1 IS less than 1).
# Fix: use JMP_A_POS/JMP_B_POS to detect differing signs before CMP.
# Note: `int` is int16 (signed per spec), so it also needs signed comparison.
# ===========================================================================


class TestSignedComparisons:
    """Signed types must use sign-aware comparisons."""

    def test_int8_neg_lt_pos(self):
        """int8: -1 < 1 must return 1 (unsigned 255 < 1 would return 0)."""
        cpu = run_c("""
            char main() {
                int8 a = -1;
                int8 b = 1;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: -1 < 1 should be 1, got {cpu.A}"

    def test_int8_pos_gt_neg(self):
        """int8: 1 > -1 must return 1."""
        cpu = run_c("""
            char main() {
                int8 a = 1;
                int8 b = -1;
                if (a > b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: 1 > -1 should be 1, got {cpu.A}"

    def test_int8_neg_le_pos(self):
        """int8: -1 <= 1 must return 1."""
        cpu = run_c("""
            char main() {
                int8 a = -1;
                int8 b = 1;
                if (a <= b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: -1 <= 1 should be 1, got {cpu.A}"

    def test_int8_pos_ge_neg(self):
        """int8: 1 >= -1 must return 1."""
        cpu = run_c("""
            char main() {
                int8 a = 1;
                int8 b = -1;
                if (a >= b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: 1 >= -1 should be 1, got {cpu.A}"

    def test_int8_same_sign_positive(self):
        """int8: 5 < 10 must return 1 (both positive, CMP path)."""
        cpu = run_c("""
            char main() {
                int8 a = 5;
                int8 b = 10;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: 5 < 10 should be 1, got {cpu.A}"

    def test_int8_same_sign_negative(self):
        """int8: -5 > -10 must return 1 (both negative: 251 > 246 unsigned, same result)."""
        cpu = run_c("""
            char main() {
                int8 a = -5;
                int8 b = -10;
                if (a > b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: -5 > -10 should be 1, got {cpu.A}"

    def test_int8_eq_still_works(self):
        """int8: -1 == -1 must return 1 (equality is sign-agnostic)."""
        cpu = run_c("""
            char main() {
                int8 a = -1;
                int8 b = -1;
                if (a == b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int8: -1 == -1 should be 1, got {cpu.A}"

    def test_int_uses_signed_cmp(self):
        """int (alias for int16, signed): -1 < 1 must return 1."""
        cpu = run_c("""
            char main() {
                int a = -1;
                int b = 1;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"int: -1 < 1 should be 1, got {cpu.A}"

    def test_int8_emits_jmp_a_pos(self):
        """int8 comparison must emit JMP_A_POS for sign-bit check."""
        lines = asm_lines("""
            char main() {
                int8 a = 1;
                int8 b = 2;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert any("JMP_A_POS" in l for l in lines), (
            "int8 comparison must emit JMP_A_POS"
        )

    def test_char_no_signed_cmp(self):
        """char comparison must NOT emit JMP_A_POS (char is unsigned)."""
        lines = asm_lines(
            "char main(char a, char b) { if (a < b) return 1; return 0; }"
        )
        assert not any("JMP_A_POS" in l for l in lines), (
            "char comparison must not emit JMP_A_POS"
        )

    def test_uint8_no_signed_cmp(self):
        """uint8 comparison must NOT emit JMP_A_POS (uint8 is unsigned)."""
        lines = asm_lines("""
            char main() {
                uint8 a = 1;
                uint8 b = 2;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert not any("JMP_A_POS" in l for l in lines), (
            "uint8 comparison must not emit JMP_A_POS"
        )


# ===========================================================================
# Integration tests: compile → assemble → simulate → verify CPU state
#
# Each test is a small but realistic program exercising multiple features
# together. These complement the per-bug unit tests above.
# ===========================================================================


class TestArithmeticAndLoops:
    """Loops, accumulators, and arithmetic."""

    def test_sum_1_to_10(self):
        """Sum 1..10 in a for loop with += must return 55."""
        cpu = run_c("""
            char main() {
                char sum = 0;
                char i;
                for (i = 1; i <= 10; i++)
                    sum += i;
                return sum;
            }
        """)
        assert cpu.A == 55, f"sum 1..10 should be 55, got {cpu.A}"

    def test_factorial_5(self):
        """5! = 120 computed via repeated addition (no multiply)."""
        cpu = run_c("""
            char main() {
                char result = 1;
                char n;
                for (n = 2; n <= 5; n++) {
                    char prev = result;
                    char i;
                    result = 0;
                    for (i = 0; i < n; i++)
                        result += prev;
                }
                return result;
            }
        """)
        assert cpu.A == 120, f"5! should be 120, got {cpu.A}"

    def test_countdown_with_break(self):
        """Count down from 10, break at 5."""
        cpu = run_c("""
            char main() {
                char x = 10;
                while (1) {
                    if (x == 5) break;
                    x--;
                }
                return x;
            }
        """)
        assert cpu.A == 5, f"should break at 5, got {cpu.A}"

    def test_bitwise_flag_toggle(self):
        """Set, clear, and toggle bits: 0 |= 0x30 &= 0xF4 ^= 0x04."""
        cpu = run_c("""
            char main() {
                char flags = 0;
                flags |= 0x30;
                flags &= 0xF4;
                flags ^= 0x04;
                return flags;
            }
        """)
        # 0x00 | 0x30 = 0x30, & 0xF4 = 0x30, ^ 0x04 = 0x34
        assert cpu.A == 0x34, f"flags should be 0x34, got {cpu.A:#x}"


class TestControlFlow:
    """Branching, continue, early return."""

    def test_nested_if_else(self):
        """Classify a value: <10 → 1, <100 → 2, else → 3."""
        cpu = run_c(
            """
            char main(char x) {
                if (x < 10) return 1;
                if (x < 100) return 2;
                return 3;
            }
        """,
            A=50,
        )
        assert cpu.A == 2, f"50 should classify as 2, got {cpu.A}"

    def test_for_with_continue(self):
        """Sum even numbers 0..9 by skipping odd with continue."""
        cpu = run_c("""
            char main() {
                char sum = 0;
                char i;
                for (i = 0; i < 10; i++) {
                    if (i & 1) continue;
                    sum += i;
                }
                return sum;
            }
        """)
        # 0+2+4+6+8 = 20
        assert cpu.A == 20, f"sum of evens 0..9 should be 20, got {cpu.A}"

    def test_while_with_early_return(self):
        """Search for value 30 in a countdown, return the iteration index."""
        cpu = run_c("""
            char main() {
                char val = 35;
                char idx = 0;
                while (val > 0) {
                    if (val == 30) return idx;
                    val--;
                    idx++;
                }
                return 255;
            }
        """)
        assert cpu.A == 5, f"should find 30 at index 5, got {cpu.A}"


class TestFunctions:
    """Function calls, return values, globals."""

    def test_function_call_and_return(self):
        """max(a,b) helper returns the larger of two values."""
        cpu = run_c("""
            char main() {
                return max(17, 42);
            }
            char max(char a, char b) {
                if (a > b) return a;
                return b;
            }
        """)
        assert cpu.A == 42, f"max(17,42) should be 42, got {cpu.A}"

    def test_chained_function_calls(self):
        """double(add1(x)): compose two functions."""
        cpu = run_c("""
            char main() {
                return double(add1(9));
            }
            char add1(char x) { return x + 1; }
            char double(char x) { return x + x; }
        """)
        # add1(9)=10, double(10)=20
        assert cpu.A == 20, f"double(add1(9)) should be 20, got {cpu.A}"

    def test_function_modifies_global(self):
        """Function writes a global, caller reads it back."""
        cpu = run_c("""
            char g;
            char main() {
                set_g(77);
                return g;
            }
            void set_g(char val) { g = val; }
        """)
        assert cpu.A == 77, f"global g should be 77, got {cpu.A}"

    def test_main_entry_point_order_independent(self):
        """main declared after helpers must still be the entry point."""
        cpu = run_c("""
            char helper() { return 42; }
            char main() { return helper(); }
        """)
        assert cpu.A == 42, f"main after helper should return 42, got {cpu.A}"


class TestInt16:
    """16-bit integer operations."""

    def test_16bit_counter(self):
        """Increment int past 255 using ++ in a char-controlled loop."""
        cpu = run_c("""
            int main() {
                int x = 250;
                char i;
                for (i = 0; i < 10; i++)
                    x++;
                return x;
            }
        """)
        # 260 = 0x0104: crosses the 8-bit boundary
        assert cpu.A == 0x04 and cpu.B == 0x01, (
            f"250+10 should be 260 (0x0104), got A={cpu.A:#x} B={cpu.B:#x}"
        )

    def test_16bit_decrement(self):
        """Decrement int below 256 using -- in a char-controlled loop."""
        cpu = run_c("""
            int main() {
                int x = 260;
                char i;
                for (i = 0; i < 10; i++)
                    x--;
                return x;
            }
        """)
        # 250 = 0x00FA: crosses back below the 8-bit boundary
        assert cpu.A == 0xFA and cpu.B == 0x00, (
            f"260-10 should be 250 (0x00FA), got A={cpu.A:#x} B={cpu.B:#x}"
        )


class TestSignedIntegration:
    """Signed types in realistic contexts."""

    def test_signed_countdown(self):
        """Count from 5 down past 0 to -3 using int8 and signed >=."""
        cpu = run_c("""
            char main() {
                int8 x = 5;
                int8 limit = -3;
                while (x >= limit) x--;
                return x;
            }
        """)
        # Loop exits when x < -3, so x == -4 == 252
        assert cpu.A == 252, f"should stop at -4 (252), got {cpu.A}"

    def test_abs_function(self):
        """Absolute value of int8 via signed < 0 check."""
        cpu = run_c("""
            char main() {
                return my_abs(-5);
            }
            char my_abs(int8 x) {
                if (x < 0) return -x;
                return x;
            }
        """)
        assert cpu.A == 5, f"abs(-5) should be 5, got {cpu.A}"


class TestShifts:
    """Shift operations."""

    def test_shift_multiply_by_8(self):
        """x << 3 should multiply by 8."""
        cpu = run_c(
            """
            char main(char x) {
                return x << 3;
            }
        """,
            A=5,
        )
        assert cpu.A == 40, f"5 << 3 should be 40, got {cpu.A}"


# ===========================================================================
# Tier 2: Logical && and || with short-circuit evaluation
#
# The lexer and parser already handle these; codegen raises CodeGenError.
# Result must always be 0 or 1 (C semantics). Right operand must not be
# evaluated when left operand already determines the result.
# ===========================================================================


class TestLogicalOperators:
    """&& and || must short-circuit and return 0 or 1."""

    # --- && ---

    def test_and_true_true(self):
        """1 && 1 must return 1."""
        cpu = run_c("char main() { if (1 && 1) return 1; return 0; }")
        assert cpu.A == 1, f"1 && 1 should be 1, got {cpu.A}"

    def test_and_true_false(self):
        """1 && 0 must return 0."""
        cpu = run_c("char main() { if (1 && 0) return 1; return 0; }")
        assert cpu.A == 0, f"1 && 0 should be 0, got {cpu.A}"

    def test_and_false_short_circuits(self):
        """0 && 1 must return 0 (left is false, right must be skipped)."""
        cpu = run_c("char main() { if (0 && 1) return 1; return 0; }")
        assert cpu.A == 0, f"0 && 1 should be 0, got {cpu.A}"

    def test_and_normalizes_to_0_or_1(self):
        """5 && 10 must return 1, not 10."""
        cpu = run_c("char main() { return 5 && 10; }")
        assert cpu.A == 1, f"5 && 10 should be 1, got {cpu.A}"

    # --- || ---

    def test_or_false_false(self):
        """0 || 0 must return 0."""
        cpu = run_c("char main() { if (0 || 0) return 1; return 0; }")
        assert cpu.A == 0, f"0 || 0 should be 0, got {cpu.A}"

    def test_or_false_true(self):
        """0 || 1 must return 1 (right determines result)."""
        cpu = run_c("char main() { if (0 || 1) return 1; return 0; }")
        assert cpu.A == 1, f"0 || 1 should be 1, got {cpu.A}"

    def test_or_true_short_circuits(self):
        """1 || 0 must return 1 (left is true, right must be skipped)."""
        cpu = run_c("char main() { if (1 || 0) return 1; return 0; }")
        assert cpu.A == 1, f"1 || 0 should be 1, got {cpu.A}"

    # --- with expression operands ---

    def test_and_with_comparisons(self):
        """(a > 0) && (b > 0) must return 1 when both positive."""
        cpu = run_c(
            """
            char main(char a, char b) {
                if (a > 0 && b > 0) return 1;
                return 0;
            }
        """,
            A=5,
            B=3,
        )
        assert cpu.A == 1, f"5>0 && 3>0 should be 1, got {cpu.A}"

    def test_or_with_comparisons(self):
        """(a == 0) || (b == 0) must return 1 when one is zero."""
        cpu = run_c(
            """
            char main(char a, char b) {
                if (a == 0 || b == 0) return 1;
                return 0;
            }
        """,
            A=0,
            B=5,
        )
        assert cpu.A == 1, f"0==0 || 5==0 should be 1, got {cpu.A}"

    def test_and_short_circuit_skips_rhs(self):
        """0 && side_effect(): global must remain 0 (RHS not evaluated)."""
        cpu = run_c("""
            char g;
            char main() {
                g = 0;
                if (0 && bump()) return 1;
                return g;
            }
            char bump() { g = 99; return 1; }
        """)
        assert cpu.A == 0, (
            f"RHS of 0 && bump() must not run; g should stay 0, got {cpu.A}"
        )

    def test_mixed_precedence(self):
        """a || b && c: && binds tighter, so a || (b && c)."""
        # a=0, b=1, c=1: 0 || (1 && 1) = 0 || 1 = 1
        # If || bound tighter: (0 || 1) && 1 = 1 && 1 = 1 -- same result
        # Use a=0, b=0, c=1: 0 || (0 && 1) = 0 || 0 = 0
        # If || bound tighter: (0 || 0) && 1 = 0 && 1 = 0 -- same again
        # Use a=1, b=0, c=0: 1 || (0 && 0) = 1 || 0 = 1
        # If && bound tighter (wrong): 1 || (0 && 0) = 1 -- can't distinguish
        # Best distinguishing case: a=0, b=1, c=0
        # Correct (&&-tighter): 0 || (1 && 0) = 0 || 0 = 0
        # Wrong (||-tighter):   (0 || 1) && 0 = 1 && 0 = 0 -- same!
        # Use: a=1, b=0, c=0 with the expression: a && b || c
        # Correct (&&-tighter): (1 && 0) || 0 = 0 || 0 = 0
        # Wrong (||-tighter):   1 && (0 || 0) = 1 && 0 = 0 -- same
        # Use: a=0, b=1, c=1 with a && b || c
        # Correct: (0 && 1) || 1 = 0 || 1 = 1
        # Wrong:    0 && (1 || 1) = 0 && 1 = 0  <-- distinguishable!
        cpu = run_c(
            """
            char main(char a, char b, char c) {
                if (a && b || c) return 1;
                return 0;
            }
        """,
            A=0,
            B=1,
        )
        # c is passed via stack (not yet supported); use only a and b
        # Rewrite: a=0, b=1 → (0 && 1) || 0 isn't testable without c
        # Simplify: just test a && b || 1 with a=0, b=1
        # (0 && 1) || 1 = 0 || 1 = 1 (correct &&-tighter)
        # 0 && (1 || 1) = 0 && 1  = 0 (wrong ||-tighter)
        cpu = run_c(
            """
            char main(char a, char b) {
                if (a && b || 1) return 1;
                return 0;
            }
        """,
            A=0,
            B=1,
        )
        assert cpu.A == 1, f"(0&&1)||1 should be 1, got {cpu.A}"


# =============================================================================
# Multiply, Divide, Modulo (Tier 2 software subroutines)
# =============================================================================


class TestMultiplyDivide:
    """Software multiply, divide, and modulo operators (* / %).

    The SK-02 has no hardware multiply/divide. The compiler emits helper
    subroutines (__rt_mul, __rt_div) at the end of the output, only when
    the operators are actually used — no bloat otherwise.
    """

    # --- structural tests ---

    def test_multiply_emits_gosub_rt_mul(self):
        """* must emit GOSUB __rt_mul."""
        lines = asm_lines("char main(char a, char b) { return a * b; }")
        assert "GOSUB __rt_mul" in lines, "* must emit GOSUB __rt_mul"

    def test_divide_emits_gosub_rt_div(self):
        """/ must emit GOSUB __rt_div."""
        lines = asm_lines("char main(char a, char b) { return a / b; }")
        assert "GOSUB __rt_div" in lines, "/ must emit GOSUB __rt_div"

    def test_modulo_emits_gosub_rt_div(self):
        """% must emit GOSUB __rt_div (reuses divide, takes remainder)."""
        lines = asm_lines("char main(char a, char b) { return a % b; }")
        assert "GOSUB __rt_div" in lines, "% must emit GOSUB __rt_div"

    def test_no_mul_routine_when_unused(self):
        """__rt_mul: must NOT appear if * is not used."""
        lines = asm_lines("char main(char a, char b) { return a + b; }")
        assert "__rt_mul:" not in lines, "__rt_mul must not be emitted when unused"

    def test_no_div_routine_when_unused(self):
        """__rt_div: must NOT appear if / and % are not used."""
        lines = asm_lines("char main(char a, char b) { return a + b; }")
        assert "__rt_div:" not in lines, "__rt_div must not be emitted when unused"

    def test_mul_routine_emitted_when_used(self):
        """__rt_mul: must appear in output when * is used."""
        lines = asm_lines("char main(char a, char b) { return a * b; }")
        assert "__rt_mul:" in lines, "__rt_mul must be emitted when * is used"

    def test_div_routine_emitted_when_used(self):
        """__rt_div: must appear in output when / is used."""
        lines = asm_lines("char main(char a, char b) { return a / b; }")
        assert "__rt_div:" in lines, "__rt_div must be emitted when / is used"

    # --- multiply runtime tests ---

    def test_multiply_3_by_7(self):
        """3 * 7 must return 21."""
        cpu = run_c("char main(char a, char b) { return a * b; }", A=3, B=7)
        assert cpu.A == 21, f"3 * 7 should be 21, got {cpu.A}"

    def test_multiply_by_zero(self):
        """5 * 0 must return 0."""
        cpu = run_c("char main(char a, char b) { return a * b; }", A=5, B=0)
        assert cpu.A == 0, f"5 * 0 should be 0, got {cpu.A}"

    def test_multiply_by_one(self):
        """7 * 1 must return 7."""
        cpu = run_c("char main(char a, char b) { return a * b; }", A=7, B=1)
        assert cpu.A == 7, f"7 * 1 should be 7, got {cpu.A}"

    def test_multiply_15_by_17(self):
        """15 * 17 = 255, max meaningful 8-bit result."""
        cpu = run_c("char main(char a, char b) { return a * b; }", A=15, B=17)
        assert cpu.A == 255, f"15 * 17 should be 255, got {cpu.A}"

    # --- divide runtime tests ---

    def test_divide_42_by_7(self):
        """42 / 7 must return 6."""
        cpu = run_c("char main(char a, char b) { return a / b; }", A=42, B=7)
        assert cpu.A == 6, f"42 / 7 should be 6, got {cpu.A}"

    def test_divide_truncates(self):
        """10 / 3 must return 3 (truncation)."""
        cpu = run_c("char main(char a, char b) { return a / b; }", A=10, B=3)
        assert cpu.A == 3, f"10 / 3 should be 3, got {cpu.A}"

    def test_divide_zero_by_n(self):
        """0 / 5 must return 0."""
        cpu = run_c("char main(char a, char b) { return a / b; }", A=0, B=5)
        assert cpu.A == 0, f"0 / 5 should be 0, got {cpu.A}"

    def test_divide_by_one(self):
        """42 / 1 must return 42."""
        cpu = run_c("char main(char a, char b) { return a / b; }", A=42, B=1)
        assert cpu.A == 42, f"42 / 1 should be 42, got {cpu.A}"

    # --- modulo runtime tests ---

    def test_modulo_10_by_3(self):
        """10 % 3 must return 1."""
        cpu = run_c("char main(char a, char b) { return a % b; }", A=10, B=3)
        assert cpu.A == 1, f"10 % 3 should be 1, got {cpu.A}"

    def test_modulo_exact_division(self):
        """42 % 7 must return 0 (exact division)."""
        cpu = run_c("char main(char a, char b) { return a % b; }", A=42, B=7)
        assert cpu.A == 0, f"42 % 7 should be 0, got {cpu.A}"

    def test_modulo_255_by_10(self):
        """255 % 10 must return 5."""
        cpu = run_c("char main(char a, char b) { return a % b; }", A=255, B=10)
        assert cpu.A == 5, f"255 % 10 should be 5, got {cpu.A}"

    # --- compound assignment tests ---

    def test_mul_assign(self):
        """x *= 3 must multiply in place."""
        cpu = run_c(
            """
            char main(char a) {
                char x;
                x = a;
                x *= 3;
                return x;
            }
        """,
            A=7,
        )
        assert cpu.A == 21, f"7 *= 3 should be 21, got {cpu.A}"

    def test_div_assign(self):
        """x /= 2 must divide in place."""
        cpu = run_c(
            """
            char main(char a) {
                char x;
                x = a;
                x /= 2;
                return x;
            }
        """,
            A=42,
        )
        assert cpu.A == 21, f"42 /= 2 should be 21, got {cpu.A}"

    def test_mod_assign(self):
        """x %= 5 must compute remainder in place."""
        cpu = run_c(
            """
            char main(char a) {
                char x;
                x = a;
                x %= 5;
                return x;
            }
        """,
            A=13,
        )
        assert cpu.A == 3, f"13 %= 5 should be 3, got {cpu.A}"


# ===========================================================================
# Stack-passed function parameters (3+)
#
# Params 1-2 go in registers A/B (8-bit) or AB/CD (16-bit).
# Params 3+ are pushed onto the data stack by the caller (right-to-left),
# and popped by the callee in declaration order.
# ===========================================================================


class TestStackPassedParams:
    """Function parameters beyond the first two must be passed on the data stack."""

    def test_three_params_no_error(self):
        """3 parameters must not raise CodeGenError."""
        asm_lines("void f(char a, char b, char c) { } void main() { f(1, 2, 3); }")

    def test_three_char_params_caller_pushes(self):
        """Calling f(1,2,3) must PUSH_A for the third arg before GOSUB."""
        lines = asm_lines("void f(char a, char b, char c); void main() { f(1, 2, 3); }")
        gosub_idx = next(i for i, l in enumerate(lines) if "GOSUB _f" in l)
        # At least one PUSH_A before the GOSUB (for the third param)
        push_before = [l for l in lines[:gosub_idx] if l == "PUSH_A"]
        assert len(push_before) >= 1, "Third param must be pushed onto data stack"

    def test_three_char_params_callee_pops(self):
        """Function with 3 char params must POP_A to receive the third."""
        lines = asm_lines("char f(char a, char b, char c) { return c; }")
        func_start = next(i for i, l in enumerate(lines) if l == "_f:")
        pop_lines = [l for l in lines[func_start:] if l == "POP_A"]
        assert len(pop_lines) >= 1, "Callee must pop third param from stack"

    def test_three_char_params_returns_third(self):
        """f(10, 20, 30) where f returns c must yield 30."""
        cpu = run_c("""
            char f(char a, char b, char c) { return c; }
            char main() { return f(10, 20, 30); }
        """)
        assert cpu.A == 30, f"Expected 30, got {cpu.A}"

    def test_three_char_params_first_param_correct(self):
        """f(10, 20, 30) where f returns a must yield 10."""
        cpu = run_c("""
            char f(char a, char b, char c) { return a; }
            char main() { return f(10, 20, 30); }
        """)
        assert cpu.A == 10, f"Expected 10, got {cpu.A}"

    def test_three_char_params_second_param_correct(self):
        """f(10, 20, 30) where f returns b must yield 20."""
        cpu = run_c("""
            char f(char a, char b, char c) { return b; }
            char main() { return f(10, 20, 30); }
        """)
        assert cpu.A == 20, f"Expected 20, got {cpu.A}"

    def test_four_char_params_sum(self):
        """f(1, 2, 3, 4) where f returns a+b+c+d must yield 10."""
        cpu = run_c("""
            char f(char a, char b, char c, char d) { return a + b + c + d; }
            char main() { return f(1, 2, 3, 4); }
        """)
        assert cpu.A == 10, f"Expected 10, got {cpu.A}"

    def test_five_char_params_sum(self):
        """f(1, 2, 3, 4, 5) where f returns a+b+c+d+e must yield 15."""
        cpu = run_c("""
            char f(char a, char b, char c, char d, char e) {
                return a + b + c + d + e;
            }
            char main() { return f(1, 2, 3, 4, 5); }
        """)
        assert cpu.A == 15, f"Expected 15, got {cpu.A}"

    def test_third_param_is_int(self):
        """Third param of type int (16-bit) must round-trip correctly."""
        cpu = run_c("""
            int f(char a, char b, int c) { return c; }
            int main() { return f(1, 2, 300); }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 300, f"Expected 300, got {result}"


# ===========================================================================
# Pointers: address-of, dereference read, dereference write
# ===========================================================================


class TestPointerAddressOf:
    """Address-of operator (&var) must emit the variable's static address."""

    def test_address_of_local_asm(self):
        """&x should emit SET_AB #_main_x."""
        lines = asm_lines("void main() { char x; char* p = &x; }")
        assert any("SET_AB #_main_x" in l for l in lines)

    def test_address_of_global_asm(self):
        """&g for global should use global label."""
        lines = asm_lines("char g; void main() { char* p = &g; }")
        assert any("SET_AB #_g" in l for l in lines)


class TestPointerDereference:
    """Dereference operator (*ptr) must read the value at the pointed-to address."""

    def test_deref_read_char(self):
        """*ptr should return the byte stored at the address."""
        cpu = run_c("""
            char main() {
                char x = 42;
                char* p = &x;
                return *p;
            }
        """)
        assert cpu.A == 42, f"Expected 42, got {cpu.A}"

    def test_deref_read_after_modify(self):
        """*ptr must reflect the current value of the variable, not the initial one."""
        cpu = run_c("""
            char main() {
                char x = 10;
                char* p = &x;
                x = 77;
                return *p;
            }
        """)
        assert cpu.A == 77, f"Expected 77, got {cpu.A}"

    def test_deref_read_int(self):
        """*ptr for int pointer should read the 16-bit value."""
        cpu = run_c("""
            int main() {
                int x = 1000;
                int* p = &x;
                return *p;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 1000, f"Expected 1000, got {result}"


class TestPointerDerefWrite:
    """Assigning through a dereferenced pointer must store to the pointed-to address."""

    def test_deref_write_char(self):
        """*ptr = val should store byte at the pointed-to address."""
        cpu = run_c("""
            char main() {
                char x = 0;
                char* p = &x;
                *p = 77;
                return x;
            }
        """)
        assert cpu.A == 77, f"Expected 77, got {cpu.A}"

    def test_deref_write_int(self):
        """*ptr = val for int pointer should store 16-bit value."""
        cpu = run_c("""
            int main() {
                int x = 0;
                int* p = &x;
                *p = 1000;
                return x;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 1000, f"Expected 1000, got {result}"

    def test_deref_write_preserves_other_vars(self):
        """Writing through pointer must not corrupt adjacent variables."""
        cpu = run_c("""
            char main() {
                char a = 11;
                char x = 0;
                char b = 22;
                char* p = &x;
                *p = 99;
                return a + b;
            }
        """)
        assert cpu.A == 33, f"Expected 33, got {cpu.A}"

    def test_deref_write_rhs_is_deref_sum(self):
        """*dest = *a + *b must read both sources and write result correctly."""
        cpu = run_c("""
            char main() {
                char a = 10;
                char b = 32;
                char dest = 0;
                char* pa = &a;
                char* pb = &b;
                char* pd = &dest;
                *pd = *pa + *pb;
                return dest;
            }
        """)
        assert cpu.A == 42, f"Expected 42, got {cpu.A}"

    def test_deref_read_modify_write(self):
        """*p = *p + 1 must increment the value at the pointed-to address."""
        cpu = run_c("""
            char main() {
                char x = 41;
                char* p = &x;
                *p = *p + 1;
                return x;
            }
        """)
        assert cpu.A == 42, f"Expected 42, got {cpu.A}"

    def test_deref_in_if_condition(self):
        """*p used as an if condition must branch correctly."""
        cpu = run_c("""
            char main() {
                char x = 1;
                char* p = &x;
                if (*p) {
                    return 10;
                }
                return 20;
            }
        """)
        assert cpu.A == 10, f"Expected 10, got {cpu.A}"

    def test_deref_in_while_condition(self):
        """Loop controlled by *p must iterate the correct number of times."""
        cpu = run_c("""
            char main() {
                char count = 3;
                char sum = 0;
                char* p = &count;
                while (*p) {
                    sum = sum + 1;
                    count = count - 1;
                }
                return sum;
            }
        """)
        assert cpu.A == 3, f"Expected 3, got {cpu.A}"

    def test_global_pointer_runtime(self):
        """Global pointer to global variable must dereference correctly at runtime."""
        cpu = run_c("""
            char g;
            char main() {
                g = 5;
                char* p = &g;
                return *p;
            }
        """)
        assert cpu.A == 5, f"Expected 5, got {cpu.A}"

    def test_pointer_as_function_param(self):
        """Passing &x to a function that writes *p should mutate x."""
        cpu = run_c("""
            void set(char* p, char val) { *p = val; }
            char main() {
                char x = 0;
                set(&x, 42);
                return x;
            }
        """)
        assert cpu.A == 42, f"Expected 42, got {cpu.A}"

    def test_double_deref(self):
        """**pp must read through two levels of indirection."""
        cpu = run_c("""
            char main() {
                char x = 7;
                char* p = &x;
                char** pp = &p;
                return **pp;
            }
        """)
        assert cpu.A == 7, f"Expected 7, got {cpu.A}"


# ===========================================================================
# BUG: 16-bit binary + and - use 8-bit ADD/SUB instead of AB+CD / AB-CD
#
# int + int must use AB+CD; int - int must use AB-CD.
# With only 8-bit ADD/SUB the high byte is silently discarded.
# ===========================================================================


class TestInt16Arithmetic:
    """16-bit (int / uint16) add and subtract must handle values > 255."""

    def test_int_add_no_carry(self):
        """int 100 + 200 = 300 (fits in low byte, sanity check)."""
        cpu = run_c("""
            int main() {
                int a = 100;
                int b = 200;
                return a + b;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 300, f"100 + 200 should be 300, got {result}"

    def test_int_add_with_carry(self):
        """int 200 + 200 = 400 — result crosses 256 boundary."""
        cpu = run_c("""
            int main() {
                int a = 200;
                int b = 200;
                return a + b;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 400, f"200 + 200 should be 400, got {result} (A={cpu.A} B={cpu.B})"

    def test_int_add_large_values(self):
        """int 500 + 300 = 800 — both operands > 255."""
        cpu = run_c("""
            int main() {
                int a = 500;
                int b = 300;
                return a + b;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 800, f"500 + 300 should be 800, got {result} (A={cpu.A} B={cpu.B})"

    def test_int_sub_no_borrow(self):
        """int 500 - 300 = 200."""
        cpu = run_c("""
            int main() {
                int a = 500;
                int b = 300;
                return a - b;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 200, f"500 - 300 should be 200, got {result}"

    def test_int_sub_with_borrow(self):
        """int 300 - 200 = 100 — crosses 256 boundary."""
        cpu = run_c("""
            int main() {
                int a = 300;
                int b = 200;
                return a - b;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 100, f"300 - 200 should be 100, got {result}"

    def test_int_add_emits_ab_plus_cd(self):
        """int + int must emit AB+CD, not ADD."""
        lines = asm_lines("""
            int main() {
                int a = 1;
                int b = 2;
                return a + b;
            }
        """)
        assert "AB+CD" in lines, "int + int should emit AB+CD"
        assert "ADD" not in lines, "int + int must not use 8-bit ADD"

    def test_int_sub_emits_ab_minus_cd(self):
        """int - int must emit AB-CD, not SUB."""
        lines = asm_lines("""
            int main() {
                int a = 3;
                int b = 2;
                return a - b;
            }
        """)
        assert "AB-CD" in lines, "int - int should emit AB-CD"
        assert "SUB" not in lines, "int - int must not use 8-bit SUB"


# ===========================================================================
# BUG: 16-bit comparisons only compare the low byte
#
# The binary-op pattern uses PUSH_A / POP_A which only preserves A (low byte).
# High byte is lost. CMP_16 is never emitted.
# ===========================================================================


class TestInt16Comparisons:
    """16-bit comparisons must use CMP_16 and compare full 16-bit values."""

    def test_uint16_eq_same_low_byte_different_high(self):
        """256 == 512 must be false (same low byte 0x00, different high bytes)."""
        cpu = run_c("""
            char main() {
                uint16 a = 256;
                uint16 b = 512;
                if (a == b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 0, f"256 == 512 should be false, got {cpu.A}"

    def test_uint16_neq_same_low_byte_different_high(self):
        """256 != 512 must be true."""
        cpu = run_c("""
            char main() {
                uint16 a = 256;
                uint16 b = 512;
                if (a != b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"256 != 512 should be true, got {cpu.A}"

    def test_uint16_lt_high_byte_matters(self):
        """256 < 512 must be true (only high bytes differ)."""
        cpu = run_c("""
            char main() {
                uint16 a = 256;
                uint16 b = 512;
                if (a < b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"256 < 512 should be true, got {cpu.A}"

    def test_uint16_gt_high_byte_matters(self):
        """512 > 256 must be true."""
        cpu = run_c("""
            char main() {
                uint16 a = 512;
                uint16 b = 256;
                if (a > b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"512 > 256 should be true, got {cpu.A}"

    def test_uint16_lte_equal_large_values(self):
        """1000 <= 1000 must be true."""
        cpu = run_c("""
            char main() {
                uint16 a = 1000;
                uint16 b = 1000;
                if (a <= b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"1000 <= 1000 should be true, got {cpu.A}"

    def test_uint16_gte_large_values(self):
        """1000 >= 500 must be true."""
        cpu = run_c("""
            char main() {
                uint16 a = 1000;
                uint16 b = 500;
                if (a >= b) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"1000 >= 500 should be true, got {cpu.A}"

    def test_int16_eq_emits_cmp_16(self):
        """int == int must emit CMP_16."""
        lines = asm_lines("""
            char main() {
                int a = 1;
                int b = 1;
                if (a == b) return 1;
                return 0;
            }
        """)
        assert "CMP_16" in lines, "int == int should emit CMP_16"


# ===========================================================================
# BUG: right shift always uses logical A>>, never arithmetic S_A>> / S_AB>>
#
# Spec: int8 >> uses S_A>> (sign-extending); uint8 >> uses A>> (logical).
# ===========================================================================


class TestArithmeticRightShift:
    """Signed right shift must preserve the sign bit."""

    def test_int8_right_shift_negative(self):
        """-4 >> 1 should give -2 (arithmetic shift preserves sign)."""
        cpu = run_c("""
            int8 main() {
                int8 x = -4;
                return x >> 1;
            }
        """)
        # -2 is 0xFE = 254 in unsigned
        assert cpu.A == 0xFE, f"-4 >> 1 should be -2 (0xFE), got {cpu.A:#04x}"

    def test_int8_right_shift_positive_unchanged(self):
        """8 >> 1 = 4 even for int8 (positive, so same as logical)."""
        cpu = run_c("""
            int8 main() {
                int8 x = 8;
                return x >> 1;
            }
        """)
        assert cpu.A == 4, f"8 >> 1 should be 4, got {cpu.A}"

    def test_int8_right_shift_emits_s_a(self):
        """int8 >> must emit S_A>> (arithmetic shift), not A>> (logical)."""
        lines = asm_lines("""
            int8 main(int8 x) {
                return x >> 1;
            }
        """)
        assert "S_A>>" in lines, "int8 >> should emit S_A>>"
        assert "A>>" not in lines, "int8 >> must not emit logical A>>"

    def test_uint8_right_shift_logical(self):
        """uint8 >> should still be logical (A>>), not arithmetic."""
        cpu = run_c("""
            char main() {
                char x = 128;
                return x >> 1;
            }
        """)
        assert cpu.A == 64, f"128 >> 1 (logical) should be 64, got {cpu.A}"

    def test_uint8_right_shift_emits_a(self):
        """uint8 >> must emit logical A>>, not S_A>>."""
        lines = asm_lines("""
            char main(char x) {
                return x >> 1;
            }
        """)
        assert "A>>" in lines, "char >> should emit A>>"


# ===========================================================================
# Untested operators: ~ (bitwise NOT), ! (logical NOT)
# ===========================================================================


class TestBitwiseNot:
    """~ operator must invert all bits."""

    def test_bitwise_not_zero(self):
        """~0 = 0xFF = 255."""
        cpu = run_c("""
            char main() {
                char x = 0;
                return ~x;
            }
        """)
        assert cpu.A == 0xFF, f"~0 should be 0xFF, got {cpu.A:#04x}"

    def test_bitwise_not_ff(self):
        """~0xFF = 0."""
        cpu = run_c("""
            char main() {
                char x = 255;
                return ~x;
            }
        """)
        assert cpu.A == 0, f"~0xFF should be 0, got {cpu.A}"

    def test_bitwise_not_nibble(self):
        """~0x0F = 0xF0."""
        cpu = run_c("""
            char main() {
                char x = 15;
                return ~x;
            }
        """)
        assert cpu.A == 0xF0, f"~0x0F should be 0xF0, got {cpu.A:#04x}"

    def test_bitwise_not_emits_not(self):
        """~ must emit NOT instruction."""
        lines = asm_lines("""
            char main(char x) {
                return ~x;
            }
        """)
        assert "NOT" in lines, "~ should emit NOT"


class TestLogicalNot:
    """! operator must return 0 or 1."""

    def test_not_nonzero_returns_zero(self):
        """!5 = 0."""
        cpu = run_c("""
            char main() {
                char x = 5;
                return !x;
            }
        """)
        assert cpu.A == 0, f"!5 should be 0, got {cpu.A}"

    def test_not_zero_returns_one(self):
        """!0 = 1."""
        cpu = run_c("""
            char main() {
                char x = 0;
                return !x;
            }
        """)
        assert cpu.A == 1, f"!0 should be 1, got {cpu.A}"

    def test_not_one_returns_zero(self):
        """!1 = 0."""
        cpu = run_c("""
            char main() {
                char x = 1;
                return !x;
            }
        """)
        assert cpu.A == 0, f"!1 should be 0, got {cpu.A}"

    def test_not_in_condition(self):
        """if (!x) must branch correctly when x = 0."""
        cpu = run_c("""
            char main() {
                char x = 0;
                if (!x) return 42;
                return 0;
            }
        """)
        assert cpu.A == 42, f"if (!0) should take branch, got {cpu.A}"

    def test_not_normalizes(self):
        """!255 = 0, !0 = 1 (result always 0 or 1, not bitwise complement)."""
        cpu = run_c("""
            char main() {
                char x = 255;
                return !x;
            }
        """)
        assert cpu.A == 0, f"!255 should be 0, got {cpu.A}"


# ===========================================================================
# Untested: >> (logical right shift for uint8/char)
# ===========================================================================


class TestRightShift:
    """Logical right shift for unsigned types."""

    def test_right_shift_by_1(self):
        """8 >> 1 = 4."""
        cpu = run_c("""
            char main() {
                char x = 8;
                return x >> 1;
            }
        """)
        assert cpu.A == 4, f"8 >> 1 should be 4, got {cpu.A}"

    def test_right_shift_by_3(self):
        """40 >> 3 = 5."""
        cpu = run_c("""
            char main() {
                char x = 40;
                return x >> 3;
            }
        """)
        assert cpu.A == 5, f"40 >> 3 should be 5, got {cpu.A}"

    def test_right_shift_zero_by_n(self):
        """0 >> 4 = 0."""
        cpu = run_c("""
            char main() {
                char x = 0;
                return x >> 4;
            }
        """)
        assert cpu.A == 0, f"0 >> 4 should be 0, got {cpu.A}"

    def test_right_shift_by_zero(self):
        """x >> 0 = x unchanged."""
        cpu = run_c("""
            char main() {
                char x = 42;
                return x >> 0;
            }
        """)
        assert cpu.A == 42, f"42 >> 0 should be 42, got {cpu.A}"

    def test_right_shift_high_bit_cleared(self):
        """128 >> 1 = 64 (logical: high bit cleared, not sign-extended)."""
        cpu = run_c("""
            char main() {
                char x = 128;
                return x >> 1;
            }
        """)
        assert cpu.A == 64, f"128 >> 1 (logical) should be 64, got {cpu.A}"


# ===========================================================================
# Untested: character literals ('A', '\n', etc.)
# ===========================================================================


class TestCharLiterals:
    """Character literals must produce their ASCII value."""

    def test_char_literal_letter(self):
        """'A' = 65."""
        cpu = run_c("""
            char main() {
                return 'A';
            }
        """)
        assert cpu.A == 65, f"'A' should be 65, got {cpu.A}"

    def test_char_literal_zero(self):
        """'\\0' = 0."""
        cpu = run_c(r"""
            char main() {
                return '\0';
            }
        """)
        assert cpu.A == 0, f"'\\0' should be 0, got {cpu.A}"

    def test_char_literal_newline(self):
        """'\\n' = 10."""
        cpu = run_c(r"""
            char main() {
                return '\n';
            }
        """)
        assert cpu.A == 10, f"'\\n' should be 10, got {cpu.A}"

    def test_char_literal_in_variable(self):
        """char x = 'Z'; return x;"""
        cpu = run_c("""
            char main() {
                char x = 'Z';
                return x;
            }
        """)
        assert cpu.A == 90, f"'Z' should be 90, got {cpu.A}"

    def test_char_literal_in_comparison(self):
        """x == 'A' works as comparison."""
        cpu = run_c("""
            char main(char x) {
                if (x == 'A') return 1;
                return 0;
            }
        """, A=65)
        assert cpu.A == 1, f"65 == 'A' should be true, got {cpu.A}"


# ===========================================================================
# Untested: global zero-initialization
# ===========================================================================


class TestGlobalInit:
    """Global variables must be zero-initialized."""

    def test_global_byte_zero_initialized(self):
        """A global char not explicitly set must read as 0."""
        cpu = run_c("""
            char g;
            char main() {
                return g;
            }
        """)
        assert cpu.A == 0, f"Uninitialized global should be 0, got {cpu.A}"

    def test_global_word_zero_initialized(self):
        """A global int not explicitly set must read as 0."""
        cpu = run_c("""
            int g;
            char main() {
                if (g == 0) return 1;
                return 0;
            }
        """)
        assert cpu.A == 1, f"Uninitialized global int should be 0, got {cpu.A}"

    def test_global_emits_byte_zero(self):
        """Global char must emit .BYTE 0 in data section."""
        lines = asm_lines("""
            char g;
            char main() { return g; }
        """)
        assert ".BYTE 0" in lines, "Global char should emit .BYTE 0"

    def test_global_emits_word_zero(self):
        """Global int must emit .WORD 0 in data section."""
        lines = asm_lines("""
            int g;
            char main() { return 0; }
        """)
        assert ".WORD 0" in lines, "Global int should emit .WORD 0"


# ===========================================================================
# Undertested: break in for loop, continue in while loop
# ===========================================================================


class TestBreakContinueVariants:
    """break and continue must work in all loop types."""

    def test_break_in_for_loop(self):
        """break must exit a for loop early."""
        cpu = run_c("""
            char main() {
                char i;
                for (i = 0; i < 10; i++) {
                    if (i == 5) break;
                }
                return i;
            }
        """)
        assert cpu.A == 5, f"break at i==5 should leave i=5, got {cpu.A}"

    def test_continue_in_while_loop(self):
        """continue must skip rest of while loop body."""
        cpu = run_c("""
            char main() {
                char i = 0;
                char sum = 0;
                while (i < 10) {
                    i++;
                    if (i == 5) continue;
                    sum++;
                }
                return sum;
            }
        """)
        # Counts 1..10 but skips increment when i==5, so 9 increments
        assert cpu.A == 9, f"continue should skip one iteration, got {cpu.A}"


# ===========================================================================
# BUG-4: <<= and >>= compound assignment cannot be lexed/parsed
# ===========================================================================


class TestShiftAssign:
    """<<= and >>= compound assignment operators."""

    def test_left_shift_assign(self):
        """x <<= 2 should multiply x by 4."""
        cpu = run_c("""
            char main() {
                char x = 3;
                x <<= 2;
                return x;
            }
        """)
        assert cpu.A == 12, f"3 <<= 2 should give 12, got {cpu.A}"

    def test_right_shift_assign(self):
        """x >>= 1 should halve x."""
        cpu = run_c("""
            char main() {
                char x = 20;
                x >>= 1;
                return x;
            }
        """)
        assert cpu.A == 10, f"20 >>= 1 should give 10, got {cpu.A}"


# ---------------------------------------------------------------------------
# Semantic analysis error tests
# ---------------------------------------------------------------------------


class TestSemanticErrors:
    """The type checker should catch errors early with clear messages."""

    def test_undefined_variable(self):
        """Referencing an undeclared variable raises SemanticError."""
        with pytest.raises(SemanticError, match="Undefined variable: x"):
            compile_string("""
                char main() {
                    return x;
                }
            """)

    def test_undefined_function(self):
        """Calling an undeclared function raises SemanticError."""
        with pytest.raises(SemanticError, match="undeclared function: foo"):
            compile_string("""
                char main() {
                    return foo(1);
                }
            """)

    def test_wrong_argument_count(self):
        """Passing wrong number of args raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 1 argument"):
            compile_string("""
                char add(char a) { return a; }
                char main() {
                    return add(1, 2);
                }
            """)

    def test_deref_non_pointer(self):
        """Dereferencing a non-pointer raises SemanticError."""
        with pytest.raises(SemanticError, match="non-pointer"):
            compile_string("""
                char main() {
                    char x = 5;
                    return *x;
                }
            """)


# ===========================================================================
# FEATURE: Arrays
#
# Fixed-size arrays: uint8 buf[N] / uint16 arr[N].
# Access via arr[i] — computes base + i*sizeof(T), loads/stores via CD/GH.
# Array name in expression context decays to pointer (base address in AB).
# ===========================================================================


class TestArrayStorage:
    """Array declarations must emit correct storage in the data section."""

    def test_global_uint8_array_emits_bytes(self):
        """Global uint8 buf[4] should emit 4 zero bytes."""
        lines = asm_lines("uint8 buf[4]; void main() {}")
        idx = next(i for i, l in enumerate(lines) if l == "_buf:")
        storage = lines[idx + 1]
        assert storage == ".BYTE 0, 0, 0, 0"

    def test_global_uint16_array_emits_words(self):
        """Global uint16 arr[3] should emit 3 zero words."""
        lines = asm_lines("uint16 arr[3]; void main() {}")
        idx = next(i for i, l in enumerate(lines) if l == "_arr:")
        storage = lines[idx + 1]
        assert storage == ".WORD 0, 0, 0"

    def test_local_uint8_array_emits_bytes(self):
        """Local uint8 buf[4] should emit 4 zero bytes."""
        lines = asm_lines("void main() { uint8 buf[4]; }")
        idx = next(i for i, l in enumerate(lines) if l == "_main_buf:")
        storage = lines[idx + 1]
        assert storage == ".BYTE 0, 0, 0, 0"

    def test_local_uint16_array_emits_words(self):
        """Local uint16 arr[2] should emit 2 zero words."""
        lines = asm_lines("void main() { uint16 arr[2]; }")
        idx = next(i for i, l in enumerate(lines) if l == "_main_arr:")
        storage = lines[idx + 1]
        assert storage == ".WORD 0, 0"


class TestArrayReadUint8:
    """Reading uint8 array elements via arr[i]."""

    def test_read_index_zero_returns_zero(self):
        """Reading from zero-initialized array at index 0 returns 0."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                return buf[0];
            }
        """)
        assert cpu.A == 0

    def test_read_constant_index(self):
        """arr[2] on a zero-initialized array returns 0."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                return buf[2];
            }
        """)
        assert cpu.A == 0

    def test_read_emits_base_address(self):
        """Array read should emit SET_AB referencing the array label."""
        lines = asm_lines("""
            uint8 buf[4];
            uint8 main() { return buf[0]; }
        """)
        assert any("SET_AB #_buf" in l for l in lines)


class TestArrayWriteUint8:
    """Writing and reading uint8 array elements."""

    def test_write_and_read_index_zero(self):
        """buf[0] = 42; return buf[0] should yield 42."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 42;
                return buf[0];
            }
        """)
        assert cpu.A == 42

    def test_write_and_read_nonzero_constant_index(self):
        """buf[2] = 99; return buf[2] should yield 99."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[2] = 99;
                return buf[2];
            }
        """)
        assert cpu.A == 99

    def test_adjacent_elements_independent(self):
        """Writing buf[1] must not corrupt buf[0]."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 10;
                buf[1] = 20;
                return buf[0];
            }
        """)
        assert cpu.A == 10

    def test_variable_index_read(self):
        """buf[i] where i is a variable must read the correct element."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 10;
                buf[1] = 20;
                buf[2] = 30;
                uint8 i = 2;
                return buf[i];
            }
        """)
        assert cpu.A == 30

    def test_variable_index_write(self):
        """buf[i] = val where i is a variable must write the correct element."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                uint8 i = 1;
                buf[i] = 55;
                return buf[1];
            }
        """)
        assert cpu.A == 55

    def test_global_array_write_and_read(self):
        """Global array element write and readback."""
        cpu = run_c("""
            uint8 buf[4];
            uint8 main() {
                buf[3] = 77;
                return buf[3];
            }
        """)
        assert cpu.A == 77


class TestArrayUint16:
    """uint16 arrays must use 2-byte elements with correct address scaling."""

    def test_write_and_read_index_zero(self):
        """uint16 arr[0] = 1000; return arr[0] should yield 1000."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[2];
                arr[0] = 1000;
                return arr[0];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 1000

    def test_second_element_at_offset_two(self):
        """arr[1] must be at byte offset 2 from base."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[3];
                arr[0] = 100;
                arr[1] = 2000;
                arr[2] = 300;
                return arr[1];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 2000

    def test_variable_index_scales_by_two(self):
        """Variable index with uint16 must scale offset by 2."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[3];
                arr[0] = 111;
                arr[1] = 222;
                arr[2] = 333;
                uint8 i = 2;
                return arr[i];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 333


class TestArrayPointerSubscript:
    """Subscript through a pointer variable: p[i] where p is uint8*."""

    def test_pointer_subscript_read(self):
        """p[2] where p points to buf should read buf[2]."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[2] = 42;
                uint8* p = buf;
                return p[2];
            }
        """)
        assert cpu.A == 42

    def test_pointer_subscript_write(self):
        """p[1] = 99 where p points to buf should write buf[1]."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                uint8* p = buf;
                p[1] = 99;
                return buf[1];
            }
        """)
        assert cpu.A == 99

    def test_16bit_index_variable(self):
        """uint16 index must not be truncated to 8 bits."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[3] = 88;
                uint16 i = 3;
                return buf[i];
            }
        """)
        assert cpu.A == 88


class TestArrayDecay:
    """Array name in expression context decays to pointer (base address)."""

    def test_array_assigned_to_pointer(self):
        """uint8* p = buf; *p should read buf[0]."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 42;
                uint8* p = buf;
                return *p;
            }
        """)
        assert cpu.A == 42

    def test_array_passed_to_function(self):
        """Passing array to function expecting uint8* should work."""
        cpu = run_c("""
            uint8 first(uint8* p) {
                return *p;
            }
            uint8 main() {
                uint8 buf[4];
                buf[0] = 77;
                return first(buf);
            }
        """)
        assert cpu.A == 77


class TestArrayIntegration:
    """End-to-end tests for realistic array usage patterns."""

    def test_loop_fill_and_sum(self):
        """Fill array in a loop, then sum all elements."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                uint8 i = 0;
                while (i < 4) {
                    buf[i] = i + 1;
                    i++;
                }
                return buf[0] + buf[1] + buf[2] + buf[3];
            }
        """)
        assert cpu.A == 10  # 1+2+3+4

    def test_linear_search(self):
        """Linear search: return index of first match."""
        cpu = run_c("""
            uint8 main() {
                uint8 data[5];
                data[0] = 10;
                data[1] = 20;
                data[2] = 30;
                data[3] = 40;
                data[4] = 50;
                uint8 target = 30;
                uint8 i = 0;
                while (i < 5) {
                    if (data[i] == target) {
                        return i;
                    }
                    i++;
                }
                return 255;
            }
        """)
        assert cpu.A == 2

    def test_uint16_accumulator(self):
        """Sum uint16 array elements in a loop."""
        cpu = run_c("""
            uint16 main() {
                uint16 vals[3];
                vals[0] = 100;
                vals[1] = 200;
                vals[2] = 300;
                uint16 sum = 0;
                uint8 i = 0;
                while (i < 3) {
                    sum = sum + vals[i];
                    i++;
                }
                return sum;
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 600

    def test_global_array_across_functions(self):
        """Global array written by one function, read by another."""
        cpu = run_c("""
            uint8 buf[4];
            void fill() {
                buf[0] = 5;
                buf[1] = 10;
                buf[2] = 15;
                buf[3] = 20;
            }
            uint8 main() {
                fill();
                return buf[2];
            }
        """)
        assert cpu.A == 15

    def test_expression_as_index(self):
        """arr[j + 1] — binary expression as array index must work."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 10;
                buf[1] = 20;
                buf[2] = 30;
                buf[3] = 40;
                uint8 j = 1;
                return buf[j + 1];
            }
        """)
        assert cpu.A == 30

    def test_bubble_sort_uint16(self):
        """uint16 bubble sort via global array and expression indices."""
        cpu = run_c("""
            uint16 arr[6];
            uint8 arr_len;

            void bubble_sort() {
                uint8 i = 0;
                while (i < arr_len - 1) {
                    uint8 j = 0;
                    while (j < arr_len - 1 - i) {
                        if (arr[j] > arr[j + 1]) {
                            uint16 tmp = arr[j];
                            arr[j] = arr[j + 1];
                            arr[j + 1] = tmp;
                        }
                        j++;
                    }
                    i++;
                }
            }

            uint16 main() {
                arr[0] = 300;
                arr[1] = 42;
                arr[2] = 1000;
                arr[3] = 7;
                arr[4] = 500;
                arr[5] = 128;
                arr_len = 6;
                bubble_sort();
                return arr[0];
            }
        """)
        assert cpu.A == 7
        assert cpu.B == 0


# ===========================================================================
# BUG: Array codegen issues found in Codex review
# ===========================================================================


class TestArrayDecayResultReg:
    """Array decay must respect the result_reg requested by the caller (P1).

    The Identifier branch for arrays always emitted SET_AB, ignoring
    result_reg. This breaks passing an array as the second argument to a
    function — the calling convention expects it in CD, but it landed in AB.
    """

    def test_array_as_second_argument(self):
        """Array passed as second param (pointer in CD) must reach callee."""
        cpu = run_c("""
            uint8 read_index(uint8 idx, uint8* p) {
                return p[idx];
            }
            uint8 main() {
                uint8 buf[4];
                buf[2] = 55;
                return read_index(2, buf);
            }
        """)
        assert cpu.A == 55

    def test_array_decay_into_cd(self):
        """Array name used as second wide arg must be moved to CD before GOSUB."""
        lines = asm_lines("""
            uint8 buf[4];
            void take(uint16 x, uint8* p) {}
            void main() { take(1, buf); }
        """)
        # Calling convention: wide param2 is evaluated into AB then AB>CD.
        assert any("SET_AB #_buf" in l for l in lines)
        assert any("AB>CD" in l for l in lines)


class TestArrayAssignmentRejected:
    """Assigning one array variable to another must be rejected (P2).

    Previously generate_assignment() accepted any Identifier target and
    treated it as a scalar, silently miscompiling array-to-array copies.
    """

    def test_whole_array_assignment_raises(self):
        """a = b where both are arrays must raise CodeGenError."""
        with pytest.raises(Exception):
            compile_string("""
                void main() {
                    uint8 a[2];
                    uint8 b[2];
                    a = b;
                }
            """)


class TestZeroLengthArrayRejected:
    """Zero-length array declarations must be rejected (P3).

    _zero_storage_directive() used `typ.size or 1`, allocating one element
    for uint8 buf[0]. Zero-length arrays should be a compile-time error.
    """

    def test_zero_length_array_raises(self):
        """uint8 buf[0] must raise an error, not silently allocate storage."""
        with pytest.raises(Exception):
            compile_string("void main() { uint8 buf[0]; }")


# ===========================================================================
# BUG: Array index evaluation clobbers base address / carry loss on scaling
# ===========================================================================


class TestArrayIndexClobber:
    """Complex 8-bit index expressions must not clobber the base in CD (P1).

    When the index expression itself performs an array access (or any other
    operation that uses CD), the parked base address was overwritten before
    the AB+CD addition, silently reading/writing the wrong element.
    """

    def test_nested_array_subscript_as_index(self):
        """buf[idxs[0]] — subscript-as-index must not corrupt buf's base."""
        cpu = run_c("""
            uint8 main() {
                uint8 idxs[3];
                uint8 buf[4];
                idxs[0] = 2;
                buf[2] = 77;
                return buf[idxs[0]];
            }
        """)
        assert cpu.A == 77

    def test_nested_index_write(self):
        """buf[idxs[1]] = val write with nested index must land in correct slot."""
        cpu = run_c("""
            uint8 main() {
                uint8 idxs[3];
                uint8 buf[4];
                idxs[1] = 3;
                buf[idxs[1]] = 55;
                return buf[3];
            }
        """)
        assert cpu.A == 55


class TestArrayUint16IndexCarry:
    """8-bit index into uint16 array must zero-extend before shifting (P2).

    The old code did A<< then 0>B, which drops the carry bit for indices
    >= 128. The correct sequence is 0>B first (zero-extend), then AB<<.
    """

    def test_large_uint8_index_uint16_array(self):
        """uint16 arr; uint8 i=200 must address offset 400, not 144."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[210];
                arr[200] = 999;
                uint8 i = 200;
                return arr[i];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 999

    def test_index_128_boundary(self):
        """index exactly 128 must not lose the shifted bit."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[130];
                arr[128] = 1234;
                uint8 i = 128;
                return arr[i];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 1234


# ===========================================================================
# BUG: _generate_array_access_read ignores result_reg
#
# Array element reads always land in A/AB, ignoring the register requested
# by the caller. This breaks f(x, buf[i]) where the calling convention
# evaluates the second 8-bit argument with result_reg="B".
# ===========================================================================


class TestArrayReadResultReg:
    """Array element reads must respect the result_reg requested by the caller."""

    def test_array_element_as_second_arg(self):
        """f(1, buf[2]) — buf[2] must reach the callee as second argument."""
        cpu = run_c("""
            uint8 add(uint8 a, uint8 b) { return a + b; }
            uint8 main() {
                uint8 buf[4];
                buf[2] = 10;
                return add(5, buf[2]);
            }
        """)
        assert cpu.A == 15

    def test_array_element_second_arg_variable_index(self):
        """f(1, buf[i]) with variable index must pass the correct value."""
        cpu = run_c("""
            uint8 add(uint8 a, uint8 b) { return a + b; }
            uint8 main() {
                uint8 buf[4];
                buf[3] = 20;
                uint8 i = 3;
                return add(7, buf[i]);
            }
        """)
        assert cpu.A == 27


# ===========================================================================
# FEATURE: Compound assignment to array elements (arr[i] += val)
# ===========================================================================


class TestArrayCompoundAssignment:
    """arr[i] += val and friends must read-modify-write the correct element."""

    def test_add_assign_constant_index(self):
        """arr[1] += 5 with constant index."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[1] = 10;
                buf[1] += 5;
                return buf[1];
            }
        """)
        assert cpu.A == 15

    def test_add_assign_variable_index(self):
        """arr[i] += 3 with variable index."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[2] = 20;
                uint8 i = 2;
                buf[i] += 3;
                return buf[2];
            }
        """)
        assert cpu.A == 23

    def test_sub_assign(self):
        """arr[0] -= 4."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 100;
                buf[0] -= 4;
                return buf[0];
            }
        """)
        assert cpu.A == 96

    def test_or_assign(self):
        """arr[0] |= 0x0F."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 0xF0;
                buf[0] |= 0x0F;
                return buf[0];
            }
        """)
        assert cpu.A == 0xFF

    def test_and_assign(self):
        """arr[0] &= 0x0F."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 0xFF;
                buf[0] &= 0x0F;
                return buf[0];
            }
        """)
        assert cpu.A == 0x0F

    def test_xor_assign(self):
        """arr[0] ^= 0xFF."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 0xAA;
                buf[0] ^= 0xFF;
                return buf[0];
            }
        """)
        assert cpu.A == 0x55

    def test_uint16_add_assign(self):
        """uint16 arr[i] += val."""
        cpu = run_c("""
            uint16 main() {
                uint16 arr[3];
                arr[1] = 1000;
                arr[1] += 500;
                return arr[1];
            }
        """)
        result = cpu.A | (cpu.B << 8)
        assert result == 1500

    def test_does_not_corrupt_neighbours(self):
        """Compound assignment to arr[1] must not touch arr[0] or arr[2]."""
        cpu = run_c("""
            uint8 main() {
                uint8 buf[4];
                buf[0] = 1;
                buf[1] = 10;
                buf[2] = 2;
                buf[1] += 5;
                return buf[0] + buf[2];
            }
        """)
        assert cpu.A == 3
