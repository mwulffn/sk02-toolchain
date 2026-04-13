"""Tests for the SK-02 Action! symbol table and type checker.

Red/green: tests written first, then implementation to pass them.
"""

import pytest

from sk02action.ast_nodes import (
    ArrayType,
    ByteType,
    CardType,
    FunctionCall,
    IntType,
    PointerType,
    StringLiteral,
)
from sk02action.lexer import Lexer
from sk02action.parser import Parser
from sk02action.symbol_table import SymbolTable
from sk02action.type_checker import SemanticError, TypeChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_program()


def check(source: str):
    """Parse and type-check source, returning the annotated AST."""
    ast = parse(source)
    TypeChecker().check(ast)
    return ast


# ===========================================================================
# Symbol Table
# ===========================================================================


class TestSymbolTable:
    """Symbol table manages global and local scopes."""

    def test_declare_global(self):
        st = SymbolTable()
        st.declare_var("x", ByteType(1, 1), size=1)
        info = st.resolve("x")
        assert info is not None
        assert isinstance(info["type"], ByteType)

    def test_declare_local(self):
        st = SymbolTable()
        st.enter_scope("foo")
        st.declare_var("x", ByteType(1, 1), size=1)
        info = st.resolve("x")
        assert info is not None
        st.exit_scope()

    def test_local_shadows_global(self):
        st = SymbolTable()
        st.declare_var("x", CardType(1, 1), size=2)
        st.enter_scope("foo")
        st.declare_var("x", ByteType(1, 1), size=1)
        info = st.resolve("x")
        assert isinstance(info["type"], ByteType)
        st.exit_scope()
        info = st.resolve("x")
        assert isinstance(info["type"], CardType)

    def test_undeclared_raises(self):
        st = SymbolTable()
        assert st.resolve("x") is None

    def test_declare_function(self):
        st = SymbolTable()
        st.declare_func("foo", params=[], return_type=None)
        info = st.resolve_func("foo")
        assert info is not None
        assert info["return_type"] is None

    def test_declare_func_with_return(self):
        st = SymbolTable()
        st.declare_func("bar", params=[], return_type=ByteType(1, 1))
        info = st.resolve_func("bar")
        assert isinstance(info["return_type"], ByteType)


# ===========================================================================
# Type Checker
# ===========================================================================


class TestTypeChecker:
    """Type checker annotates resolved_type and catches semantic errors."""

    def test_number_literal_byte(self):
        """Numbers < 256 resolve to BYTE."""
        ast = check("BYTE FUNC F()\nRETURN(42)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, ByteType)

    def test_number_literal_card(self):
        """Numbers >= 256 resolve to CARD."""
        ast = check("CARD FUNC F()\nRETURN(1000)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, CardType)

    def test_identifier_type(self):
        ast = check("PROC Main()\n  BYTE x\n  x = 5\nRETURN")
        stmt = ast.declarations[0].body[0]
        assert isinstance(stmt.value.resolved_type, ByteType)

    def test_binary_byte_byte(self):
        """BYTE + BYTE → BYTE."""
        ast = check("BYTE FUNC F(BYTE a, BYTE b)\nRETURN(a + b)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, ByteType)

    def test_binary_byte_card(self):
        """BYTE + CARD → CARD (widening)."""
        ast = check("CARD FUNC F(BYTE a, CARD b)\nRETURN(a + b)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, CardType)

    def test_relational_produces_byte(self):
        """Relational operators always produce BYTE."""
        ast = check("BYTE FUNC F(CARD a, CARD b)\nRETURN(a > b)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, ByteType)

    def test_undeclared_variable_error(self):
        with pytest.raises(SemanticError, match="Undeclared"):
            check("PROC Main()\n  x = 5\nRETURN")

    def test_undeclared_function_error(self):
        with pytest.raises(SemanticError, match="Undeclared"):
            check("PROC Main()\n  Foo()\nRETURN")

    def test_wrong_arg_count(self):
        with pytest.raises(SemanticError, match="argument"):
            check("PROC Foo(BYTE a)\nRETURN\nPROC Main()\n  Foo(1, 2)\nRETURN")

    def test_function_call_type(self):
        """Function call resolves to the function's return type."""
        ast = check("BYTE FUNC Get5()\nRETURN(5)\nBYTE FUNC F()\nRETURN(Get5())")
        val = ast.declarations[1].return_value
        assert isinstance(val, FunctionCall)
        assert isinstance(val.resolved_type, ByteType)

    def test_param_visible_in_body(self):
        """Parameters are in scope within the routine body."""
        ast = check("PROC Foo(BYTE a)\n  a = 1\nRETURN")
        stmt = ast.declarations[0].body[0]
        assert isinstance(stmt.target.resolved_type, ByteType)


class TestTypeWidening:
    """Type widening rules: 16-bit wins over 8-bit."""

    def test_card_plus_byte(self):
        ast = check("CARD FUNC F(CARD a, BYTE b)\nRETURN(a + b)")
        assert isinstance(ast.declarations[0].return_value.resolved_type, CardType)

    def test_int_plus_byte(self):
        ast = check("INT FUNC F(INT a, BYTE b)\nRETURN(a + b)")
        assert isinstance(ast.declarations[0].return_value.resolved_type, IntType)

    def test_int_plus_card(self):
        """INT + CARD → INT (both 16-bit, INT wins for signed context)."""
        ast = check("INT FUNC F(INT a, CARD b)\nRETURN(a + b)")
        assert isinstance(ast.declarations[0].return_value.resolved_type, IntType)

    def test_nested_widening(self):
        """(BYTE + CARD) + BYTE → CARD."""
        ast = check("CARD FUNC F(BYTE a, CARD b, BYTE c)\nRETURN(a + b + c)")
        val = ast.declarations[0].return_value
        assert isinstance(val.resolved_type, CardType)


# ===========================================================================
# Pointer type rules
# ===========================================================================


class TestPointerTypes:
    """Pointer declarations, address-of, and dereference type rules."""

    def test_pointer_decl_type(self):
        """BYTE POINTER bp has PointerType(ByteType)."""
        ast = check("BYTE POINTER bp\nPROC Main()\nRETURN")
        decl = ast.declarations[0]
        assert isinstance(decl.type, PointerType)
        assert isinstance(decl.type.base_type, ByteType)

    def test_address_of_type(self):
        """@x where x:BYTE produces PointerType(ByteType)."""
        ast = check("BYTE x\nBYTE POINTER bp\nPROC Main()\n  bp = @x\nRETURN")
        main = ast.declarations[2]
        stmt = main.body[0]
        assert isinstance(stmt.value.resolved_type, PointerType)
        assert isinstance(stmt.value.resolved_type.base_type, ByteType)

    def test_dereference_type(self):
        """bp^ where bp:BYTE POINTER produces ByteType."""
        ast = check("BYTE POINTER bp\nPROC Main()\n  BYTE x\n  x = bp^\nRETURN")
        main = ast.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt.value.resolved_type, ByteType)

    def test_card_pointer_deref_type(self):
        """cp^ where cp:CARD POINTER produces CardType."""
        ast = check("CARD POINTER cp\nPROC Main()\n  CARD x\n  x = cp^\nRETURN")
        main = ast.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt.value.resolved_type, CardType)


# ===========================================================================
# Array type rules
# ===========================================================================


class TestArrayTypes:
    """Array declarations and element access type rules."""

    def test_array_decl_type(self):
        """BYTE ARRAY buf(10) has ArrayType(ByteType, size=10)."""
        ast = check("BYTE ARRAY buf(10)\nPROC Main()\nRETURN")
        decl = ast.declarations[0]
        assert isinstance(decl.type, ArrayType)
        assert isinstance(decl.type.base_type, ByteType)
        assert decl.type.size == 10

    def test_byte_array_access_type(self):
        """buf(i) where buf:BYTE ARRAY produces ByteType."""
        ast = check(
            "BYTE ARRAY buf(10)\nPROC Main()\n  BYTE x, i\n  x = buf(i)\nRETURN"
        )
        main = ast.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt.value.resolved_type, ByteType)

    def test_card_array_access_type(self):
        """tbl(i) where tbl:CARD ARRAY produces CardType."""
        ast = check(
            "CARD ARRAY tbl(10)\nPROC Main()\n  CARD x, i\n  x = tbl(i)\nRETURN"
        )
        main = ast.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt.value.resolved_type, CardType)


# ===========================================================================
# I/O Intrinsics
# ===========================================================================


class TestIntrinsics:
    """I/O intrinsics are predeclared and type-check correctly."""

    def test_readx_callable_without_declaration(self):
        """ReadX() is predeclared — no SemanticError."""
        check("PROC Main()\n  BYTE x\n  x = ReadX()\nRETURN")

    def test_ready_callable_without_declaration(self):
        """ReadY() is predeclared — no SemanticError."""
        check("PROC Main()\n  BYTE y\n  y = ReadY()\nRETURN")

    def test_gpioread_callable_without_declaration(self):
        """GpioRead() is predeclared — no SemanticError."""
        check("PROC Main()\n  BYTE g\n  g = GpioRead()\nRETURN")

    def test_gpiowrite_callable_without_declaration(self):
        """GpioWrite(val) is predeclared — no SemanticError."""
        check("PROC Main()\n  GpioWrite(42)\nRETURN")

    def test_out0write_callable_without_declaration(self):
        """Out0Write(val) is predeclared — no SemanticError."""
        check("PROC Main()\n  Out0Write(1)\nRETURN")

    def test_out1write_callable_without_declaration(self):
        """Out1Write(val) is predeclared — no SemanticError."""
        check("PROC Main()\n  Out1Write(2)\nRETURN")

    def test_outwrite_callable_without_declaration(self):
        """OutWrite(lo, hi) is predeclared — no SemanticError."""
        check("PROC Main()\n  OutWrite(1, 2)\nRETURN")

    def test_hwivalue_callable_without_declaration(self):
        """HwiValue() is predeclared — no SemanticError."""
        check("PROC Main()\n  BYTE v\n  v = HwiValue()\nRETURN")

    def test_triggerhwi_callable_without_declaration(self):
        """TriggerHwi() is predeclared — no SemanticError."""
        check("PROC Main()\n  TriggerHwi()\nRETURN")

    def test_clearinterrupt_callable_without_declaration(self):
        """ClearInterrupt() is predeclared — no SemanticError."""
        check("PROC Main()\n  ClearInterrupt()\nRETURN")

    def test_interruptflag_callable_without_declaration(self):
        """InterruptFlag() is predeclared — no SemanticError."""
        check("PROC Main()\n  BYTE f\n  f = InterruptFlag()\nRETURN")

    def test_readx_returns_byte(self):
        """ReadX() return type is ByteType."""
        ast = check("PROC Main()\n  BYTE x\n  x = ReadX()\nRETURN")
        stmt = ast.declarations[0].body[0]
        assert isinstance(stmt.value.resolved_type, ByteType)

    def test_gpioread_returns_byte(self):
        """GpioRead() return type is ByteType."""
        ast = check("PROC Main()\n  BYTE g\n  g = GpioRead()\nRETURN")
        stmt = ast.declarations[0].body[0]
        assert isinstance(stmt.value.resolved_type, ByteType)

    def test_wrong_arg_count_intrinsic(self):
        """Calling ReadX(1) raises SemanticError."""
        with pytest.raises(SemanticError):
            check("PROC Main()\n  BYTE x\n  x = ReadX(1)\nRETURN")

    def test_gpiowrite_wrong_arg_count(self):
        """Calling GpioWrite() with no args raises SemanticError."""
        with pytest.raises(SemanticError):
            check("PROC Main()\n  GpioWrite()\nRETURN")

    def test_outwrite_wrong_arg_count(self):
        """Calling OutWrite(1) with only one arg raises SemanticError."""
        with pytest.raises(SemanticError):
            check("PROC Main()\n  OutWrite(1)\nRETURN")

    def test_user_proc_shadowing_intrinsic_errors(self):
        """Declaring PROC with an intrinsic name raises SemanticError."""
        with pytest.raises(SemanticError, match="reserved"):
            check("PROC ReadX()\nRETURN\nPROC Main()\nRETURN")

    def test_user_func_shadowing_intrinsic_errors(self):
        """Declaring FUNC with an intrinsic name raises SemanticError."""
        with pytest.raises(SemanticError, match="reserved"):
            check("BYTE FUNC GpioRead()\nRETURN(0)\nPROC Main()\nRETURN")


# ===========================================================================
# SET directive type checking
# ===========================================================================


class TestSetDirectiveTypes:
    """SET directive validates identifier references."""

    def test_set_numeric_value_ok(self):
        """SET with a numeric value requires no identifier lookup."""
        check("PROC Main()\nRETURN\nSET $FFFE = 42")

    def test_set_declared_proc_ok(self):
        """SET with a declared PROC name passes type checking."""
        check("PROC Main()\nRETURN\nSET $FFFE = main")

    def test_set_undeclared_identifier_error(self):
        """SET with an undeclared name raises SemanticError."""
        with pytest.raises(SemanticError):
            check("PROC Main()\nRETURN\nSET $FFFE = undeclared_func")

    def test_set_intrinsic_identifier_error(self):
        """SET with an intrinsic name raises SemanticError (no label emitted)."""
        with pytest.raises(SemanticError, match="intrinsic"):
            check("PROC Main()\nRETURN\nSET $FFFE = ReadX")


# ===========================================================================
# String literal type checking
# ===========================================================================


class TestStringLiteralTypes:
    """String literals in expressions type as PointerType(ByteType)."""

    def test_string_literal_types_to_pointer(self):
        """p = "Hi" — RHS resolves to PointerType(ByteType)."""
        ast = check('BYTE POINTER p\nPROC Main()\n  p = "Hi"\nRETURN')
        stmt = ast.declarations[1].body[0]
        assert isinstance(stmt.value, StringLiteral)
        assert isinstance(stmt.value.resolved_type, PointerType)
        assert isinstance(stmt.value.resolved_type.base_type, ByteType)

    def test_string_literal_too_long_error(self):
        """String literal longer than 255 chars raises SemanticError."""
        long_str = "A" * 256
        with pytest.raises(SemanticError):
            check(f'BYTE POINTER p\nPROC Main()\n  p = "{long_str}"\nRETURN')

    def test_string_literal_255_chars_ok(self):
        """String literal of exactly 255 chars passes type checking."""
        s = "X" * 255
        check(f'BYTE POINTER p\nPROC Main()\n  p = "{s}"\nRETURN')

    def test_empty_string_ok(self):
        """Empty string literal passes type checking."""
        check('BYTE POINTER p\nPROC Main()\n  p = ""\nRETURN')
