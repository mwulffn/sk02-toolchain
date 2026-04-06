"""Tests for the SK-02 Action! constant folding pass.

Red/green: tests written first, then implementation to pass them.
"""

from sk02action.ast_nodes import (
    BinaryOp,
    CardType,
    NumberLiteral,
)
from sk02action.const_fold import ConstantFolder
from sk02action.lexer import Lexer
from sk02action.parser import Parser
from sk02action.type_checker import TypeChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fold(source: str):
    """Parse, type-check, fold, and return the AST."""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse_program()
    TypeChecker().check(ast)
    ConstantFolder().fold(ast)
    return ast


def return_value(source: str):
    """Get the return value expression from a single-func program after folding."""
    ast = fold(source)
    return ast.declarations[0].return_value


# ===========================================================================
# Basic folding
# ===========================================================================


class TestConstantFolding:
    """Constant expressions are folded to single NumberLiterals."""

    def test_add(self):
        val = return_value("BYTE FUNC F()\nRETURN(3 + 4)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 7

    def test_subtract(self):
        val = return_value("BYTE FUNC F()\nRETURN(10 - 3)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 7

    def test_multiply(self):
        val = return_value("BYTE FUNC F()\nRETURN(6 * 7)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 42

    def test_divide(self):
        val = return_value("BYTE FUNC F()\nRETURN(10 / 3)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 3

    def test_mod(self):
        val = return_value("BYTE FUNC F()\nRETURN(10 MOD 3)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 1

    def test_lsh(self):
        val = return_value("BYTE FUNC F()\nRETURN(1 LSH 4)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 16

    def test_rsh(self):
        val = return_value("BYTE FUNC F()\nRETURN(16 RSH 2)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 4

    def test_bitwise_and(self):
        val = return_value("BYTE FUNC F()\nRETURN($FF AND $0F)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 15

    def test_bitwise_or(self):
        val = return_value("BYTE FUNC F()\nRETURN($F0 OR $0F)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 255

    def test_bitwise_xor(self):
        val = return_value("BYTE FUNC F()\nRETURN($FF XOR $0F)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 240

    def test_nested(self):
        val = return_value("BYTE FUNC F()\nRETURN((2 + 3) * 4)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 20

    def test_relational_true(self):
        val = return_value("BYTE FUNC F()\nRETURN(5 > 3)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 1

    def test_relational_false(self):
        val = return_value("BYTE FUNC F()\nRETURN(3 > 5)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 0

    def test_equality(self):
        val = return_value("BYTE FUNC F()\nRETURN(5 = 5)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 1

    def test_unary_negate(self):
        """Unary minus on constant folds."""
        val = return_value("INT FUNC F()\nRETURN(-5)")
        assert isinstance(val, NumberLiteral)
        assert val.value == -5

    def test_unary_bitwise_not(self):
        val = return_value("BYTE FUNC F()\nRETURN(%$F0)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 0x0F  # ~0xF0 masked to 8 bits


# ===========================================================================
# No-fold cases
# ===========================================================================


class TestNoFold:
    """Expressions with non-constant operands are not folded."""

    def test_identifier_not_folded(self):
        val = return_value("BYTE FUNC F(BYTE x)\nRETURN(x + 1)")
        assert isinstance(val, BinaryOp)

    def test_mixed_not_folded(self):
        val = return_value("BYTE FUNC F(BYTE x)\nRETURN(x + 3)")
        assert isinstance(val, BinaryOp)
        # But the constant operand should still be a NumberLiteral
        assert isinstance(val.right, NumberLiteral)


# ===========================================================================
# Overflow masking
# ===========================================================================


class TestOverflow:
    """Constant folding respects type-width overflow."""

    def test_byte_overflow(self):
        """200 + 200 as BYTE wraps to 144."""
        val = return_value("BYTE FUNC F()\nRETURN(200 + 200)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 144

    def test_card_no_overflow(self):
        """200 + 200 as CARD does not wrap (both operands widened to CARD)."""
        val = return_value("CARD FUNC F(CARD x)\nRETURN(x + 200)")
        # Can't fully fold since x is not constant, but the type is CARD
        assert isinstance(val, BinaryOp)
        assert isinstance(val.resolved_type, CardType)

    def test_card_overflow(self):
        """65535 + 1 as CARD wraps to 0."""
        val = return_value("CARD FUNC F()\nRETURN(65535 + 1)")
        assert isinstance(val, NumberLiteral)
        assert val.value == 0
