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
