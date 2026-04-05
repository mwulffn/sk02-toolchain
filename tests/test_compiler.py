"""Tests for the SK02-C compiler.

Each test class targets a known bug. Tests are written red-first: they describe
the correct behaviour and will fail until the bug is fixed.

Helper: `asm_lines(source)` compiles C source and returns a list of non-empty,
non-comment assembly lines for easy assertion.
"""

import pytest
from sk02cc.compiler import compile_string


def asm_lines(source: str) -> list[str]:
    """Compile C source and return stripped, non-empty, non-comment lines."""
    output = compile_string(source)
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.strip().startswith(";")
    ]


# ===========================================================================
# BUG 1: CMP flag semantics inverted
#
# The simulator sets overflow=True when A < B (i.e. result < 0).
# So after CMP:
#   A <  B  → overflow set,   zero clear
#   A == B  → overflow clear, zero set
#   A >  B  → overflow clear, zero clear
#
# The codegen docstring says the opposite. All four inequality operators
# currently produce inverted results.
# ===========================================================================

class TestCmpSemantics:
    """CMP-based comparisons must match the simulator's flag behaviour."""

    def test_less_than_uses_jmp_over_for_true(self):
        """A < B: overflow is SET when A < B, so the true-branch must JMP_OVER."""
        src = """
        char f(char a, char b) {
            if (a < b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        # The first conditional jump after CMP must branch to the TRUE label on overflow
        first_jump = lines[cmp_idx + 1]
        assert first_jump.startswith("JMP_OVER"), (
            f"'a < b' true-branch should be JMP_OVER, got: {first_jump}"
        )

    def test_greater_than_true_branch(self):
        """A > B: overflow clear AND zero clear → need to skip when overflow OR zero."""
        src = """
        char f(char a, char b) {
            if (a > b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        after_cmp = lines[cmp_idx + 1 :]
        # Must skip to false when overflow set (A < B) or zero set (A == B)
        assert any(l.startswith("JMP_OVER") for l in after_cmp[:4]), (
            "a > b must jump away on overflow (A < B case)"
        )
        assert any(l.startswith("JMP_ZERO") for l in after_cmp[:4]), (
            "a > b must jump away on zero (A == B case)"
        )

    def test_less_than_or_equal_true_branch(self):
        """A <= B: true when overflow set (A < B) OR zero set (A == B)."""
        src = """
        char f(char a, char b) {
            if (a <= b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        after_cmp = lines[cmp_idx + 1 :]
        assert any(l.startswith("JMP_ZERO") for l in after_cmp[:4]), (
            "a <= b must take true-branch on zero (A == B)"
        )
        assert any(l.startswith("JMP_OVER") for l in after_cmp[:4]), (
            "a <= b must take true-branch on overflow (A < B)"
        )

    def test_greater_than_or_equal_uses_jmp_over_for_false(self):
        """A >= B: false only when overflow set (A < B), so JMP_OVER goes to false."""
        src = """
        char f(char a, char b) {
            if (a >= b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        # First branch after CMP should skip true-branch (i.e. go to false) on overflow
        first_jump = lines[cmp_idx + 1]
        assert first_jump.startswith("JMP_OVER"), (
            f"a >= b false-branch should be JMP_OVER (A < B), got: {first_jump}"
        )

    def test_equal_uses_jmp_zero(self):
        """== still uses zero flag — must not be broken by the fix."""
        src = """
        char f(char a, char b) {
            if (a == b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        first_jump = lines[cmp_idx + 1]
        assert first_jump.startswith("JMP_ZERO"), (
            f"a == b true-branch should be JMP_ZERO, got: {first_jump}"
        )

    def test_not_equal_uses_jmp_zero_to_skip(self):
        """!= uses zero flag to skip to false, then unconditional jump to true."""
        src = """
        char f(char a, char b) {
            if (a != b) return 1;
            return 0;
        }
        """
        lines = asm_lines(src)
        cmp_idx = lines.index("CMP")
        first_jump = lines[cmp_idx + 1]
        assert first_jump.startswith("JMP_ZERO"), (
            f"a != b should JMP_ZERO to false label, got: {first_jump}"
        )


# ===========================================================================
# BUG 2: Compound assignment operators silently act as plain =
#
# generate_assignment ignores expr.op entirely. x += 5 emits the same code
# as x = 5 — it evaluates the RHS and stores it without reading the LHS first.
# ===========================================================================

class TestCompoundAssignment:
    """Compound assignments must read-modify-write, not just write."""

    def test_plus_assign_loads_variable_first(self):
        """x += 5 must load x, add 5, then store — not just store 5."""
        src = """
        void f() {
            char x;
            x = 3;
            x += 5;
        }
        """
        lines = asm_lines(src)
        # Find the x += 5 section: must see LOAD_A before STORE_A for that statement
        store_indices = [i for i, l in enumerate(lines) if l.startswith("STORE_A")]
        load_indices = [i for i, l in enumerate(lines) if l.startswith("LOAD_A")]
        # There must be a LOAD of x that precedes the final STORE of x (for +=)
        assert any(
            any(li < si for li in load_indices)
            for si in store_indices
        ), "x += 5 must load x before storing result"

    def test_plus_assign_emits_add(self):
        """x += 5 must emit an ADD instruction."""
        src = """
        void f() {
            char x;
            x += 5;
        }
        """
        lines = asm_lines(src)
        assert "ADD" in lines, "x += 5 must emit ADD"

    def test_minus_assign_emits_sub(self):
        """x -= 3 must emit a SUB instruction."""
        src = """
        void f() {
            char x;
            x -= 3;
        }
        """
        lines = asm_lines(src)
        assert "SUB" in lines, "x -= 3 must emit SUB"

    def test_and_assign_emits_and(self):
        """x &= 0x0F must emit AND."""
        src = """
        void f() {
            char x;
            x &= 15;
        }
        """
        lines = asm_lines(src)
        assert "AND" in lines, "x &= 15 must emit AND"

    def test_or_assign_emits_or(self):
        """x |= 0x80 must emit OR."""
        src = """
        void f() {
            char x;
            x |= 128;
        }
        """
        lines = asm_lines(src)
        assert "OR" in lines, "x |= 128 must emit OR"

    def test_xor_assign_emits_xor(self):
        """x ^= 0xFF must emit XOR."""
        src = """
        void f() {
            char x;
            x ^= 255;
        }
        """
        lines = asm_lines(src)
        assert "XOR" in lines, "x ^= 255 must emit XOR"


# ===========================================================================
# BUG 3: 16-bit local variable initializer only stores the low byte
#
# VariableDeclaration handling in generate_statement always emits STORE_A
# (8-bit) even for int (16-bit) locals. Should emit ST_AB_CD for int.
# ===========================================================================

class TestInt16LocalInit:
    """int local variable initializers must store both bytes."""

    def test_int_local_init_uses_16bit_store(self):
        """int x = 1000 must emit ST_AB_CD, not STORE_A."""
        src = """
        void f() {
            int x = 1000;
        }
        """
        lines = asm_lines(src)
        assert "ST_AB_CD" in lines, "int local init must use ST_AB_CD (16-bit store)"
        # Should NOT use 8-bit STORE_A for this declaration
        # (STORE_A may appear for other reasons, so we just assert the 16-bit path exists)

    def test_int_local_init_sets_pointer(self):
        """int x = 1000 must load the address of x into CD before storing."""
        src = """
        void f() {
            int x = 1000;
        }
        """
        lines = asm_lines(src)
        cd_lines = [l for l in lines if l.startswith("SET_CD")]
        assert any("_f_x" in l for l in cd_lines), (
            "int local init must SET_CD to address of x before ST_AB_CD"
        )

    def test_int_local_zero_init_uses_16bit_store(self):
        """int x = 0 must still use 16-bit store path."""
        src = """
        void f() {
            int x = 0;
        }
        """
        lines = asm_lines(src)
        assert "ST_AB_CD" in lines, "int x = 0 must use ST_AB_CD"


# ===========================================================================
# BUG 4: result_reg ignored for non-literal RHS in binary operations
#
# generate_expression(..., "B") is called for the RHS of a binary op, but
# Identifier/BinaryOp/FunctionCall all ignore result_reg and always put their
# result in A. This clobbers the left operand that was saved in A before the
# PUSH_A, meaning after POP_A the wrong value is in B for the ALU op.
#
# Correct pattern for  a + b  (both variables):
#   LOAD_A _f_a        ; left → A
#   PUSH_A             ; save left
#   LOAD_A _f_b        ; right → A  (can't go to B directly)
#   A>B                ; move right to B
#   POP_A              ; restore left
#   ADD
# ===========================================================================

class TestBinaryOpRhsRegister:
    """Binary ops with variable RHS must move result to B before the ALU op."""

    def test_add_two_variables_moves_rhs_to_b(self):
        """a + b: RHS variable must end up in B via A>B before ADD."""
        src = """
        char f(char a, char b) {
            return a + b;
        }
        """
        lines = asm_lines(src)
        add_idx = lines.index("ADD")
        # The instruction immediately before ADD (after POP_A) should be the ALU op
        # but crucially A>B must appear between the RHS load and POP_A
        pop_idx = next(i for i in range(add_idx - 1, -1, -1) if lines[i] == "POP_A")
        between = lines[pop_idx + 1 : add_idx]
        # After POP_A restores left into A, B should already have right value.
        # The A>B transfer must happen BEFORE POP_A.
        pre_pop = lines[:pop_idx]
        assert "A>B" in pre_pop, (
            "RHS variable must be transferred to B (A>B) before POP_A restores left"
        )

    def test_sub_two_variables_moves_rhs_to_b(self):
        """a - b: same pattern, RHS must be in B before SUB."""
        src = """
        char f(char a, char b) {
            return a - b;
        }
        """
        lines = asm_lines(src)
        sub_idx = lines.index("SUB")
        pop_idx = next(i for i in range(sub_idx - 1, -1, -1) if lines[i] == "POP_A")
        pre_pop = lines[:pop_idx]
        assert "A>B" in pre_pop, (
            "RHS variable must be transferred to B (A>B) before POP_A restores left"
        )

    def test_literal_rhs_still_uses_set_b(self):
        """a + 1: literal RHS should still use SET_B (existing correct path)."""
        src = """
        char f(char a) {
            return a + 1;
        }
        """
        lines = asm_lines(src)
        assert "SET_B #1" in lines, "Literal RHS should use SET_B directly"
