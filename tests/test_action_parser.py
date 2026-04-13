"""Tests for the SK-02 Action! parser.

Red/green: tests written first, then parser implemented to pass them.
Two helpers:
- parse(source): tokenize + parse → Program AST
- parse_expr(source): parse a standalone expression (wrapped in a FUNC)
"""

import pytest

from sk02action.ast_nodes import (
    ArrayAccess,
    ArrayType,
    AssignmentStmt,
    BinaryOp,
    ByteType,
    CardType,
    CharConstant,
    Dereference,
    FuncDecl,
    FunctionCall,
    Identifier,
    IfStmt,
    IntType,
    NumberLiteral,
    Parameter,
    PointerType,
    ProcCall,
    ProcDecl,
    Program,
    ReturnStmt,
    SetDirective,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileLoop,
)
from sk02action.lexer import Lexer
from sk02action.parser import ParseError, Parser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(source: str) -> Program:
    """Tokenize and parse source into a Program AST."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_program()


# ===========================================================================
# Variable declarations
# ===========================================================================


class TestParseVarDecls:
    """Parse variable declarations with types, addresses, and initializers."""

    def test_single_byte(self):
        prog = parse("BYTE x")
        assert len(prog.declarations) == 1
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, ByteType)
        assert decl.name == "x"
        assert decl.address is None
        assert decl.initial_value is None

    def test_multiple_vars(self):
        prog = parse("BYTE top, hat")
        assert len(prog.declarations) == 2
        assert prog.declarations[0].name == "top"
        assert prog.declarations[1].name == "hat"
        assert all(isinstance(d.type, ByteType) for d in prog.declarations)

    def test_card_type(self):
        prog = parse("CARD counter")
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, CardType)

    def test_int_type(self):
        prog = parse("INT num")
        decl = prog.declarations[0]
        assert isinstance(decl.type, IntType)

    def test_address_placement(self):
        prog = parse("BYTE x=$8000")
        decl = prog.declarations[0]
        assert decl.address == 0x8000

    def test_address_placement_decimal(self):
        prog = parse("BYTE x=100")
        decl = prog.declarations[0]
        assert decl.address == 100

    def test_initializer(self):
        prog = parse("INT num=[0]")
        decl = prog.declarations[0]
        assert decl.initial_value == 0

    def test_initializer_hex(self):
        prog = parse("CARD ctr=[$83D4]")
        decl = prog.declarations[0]
        assert decl.initial_value == 0x83D4

    def test_multiple_with_initializers(self):
        prog = parse("CARD a=[0], b=[1000], c=[3000]")
        assert len(prog.declarations) == 3
        assert prog.declarations[0].initial_value == 0
        assert prog.declarations[1].initial_value == 1000
        assert prog.declarations[2].initial_value == 3000


# ===========================================================================
# PROC declarations
# ===========================================================================


class TestParseProcDecl:
    """Parse PROC declarations with params, locals, and empty bodies."""

    def test_empty_proc(self):
        prog = parse("PROC Main()\nRETURN")
        assert len(prog.declarations) == 1
        proc = prog.declarations[0]
        assert isinstance(proc, ProcDecl)
        assert proc.name == "main"
        assert proc.params == []
        assert proc.locals == []
        assert proc.body == []

    def test_proc_with_params(self):
        prog = parse("PROC Foo(BYTE a, CARD b)\nRETURN")
        proc = prog.declarations[0]
        assert len(proc.params) == 2
        assert isinstance(proc.params[0], Parameter)
        assert proc.params[0].name == "a"
        assert isinstance(proc.params[0].type, ByteType)
        assert proc.params[1].name == "b"
        assert isinstance(proc.params[1].type, CardType)

    def test_proc_with_locals(self):
        prog = parse("PROC Foo()\n  BYTE x\n  CARD y\nRETURN")
        proc = prog.declarations[0]
        assert len(proc.locals) == 2
        assert proc.locals[0].name == "x"
        assert proc.locals[1].name == "y"


# ===========================================================================
# FUNC declarations
# ===========================================================================


class TestParseFuncDecl:
    """Parse FUNC declarations with return type."""

    def test_byte_func(self):
        prog = parse("BYTE FUNC Get5()\nRETURN(5)")
        assert len(prog.declarations) == 1
        func = prog.declarations[0]
        assert isinstance(func, FuncDecl)
        assert func.name == "get5"
        assert isinstance(func.return_type, ByteType)

    def test_func_with_params(self):
        prog = parse("BYTE FUNC Max(BYTE a, BYTE b)\nRETURN(a)")
        func = prog.declarations[0]
        assert len(func.params) == 2
        assert func.params[0].name == "a"
        assert func.params[1].name == "b"

    def test_card_func(self):
        prog = parse("CARD FUNC Double(CARD x)\nRETURN(x + x)")
        func = prog.declarations[0]
        assert isinstance(func.return_type, CardType)

    def test_func_return_expr(self):
        """FUNC RETURN must have parenthesized expression."""
        prog = parse("BYTE FUNC Get5()\nRETURN(5)")
        func = prog.declarations[0]
        # The last statement should be a ReturnStmt with a value
        assert len(func.body) == 0  # no statements before final RETURN
        assert func.return_value is not None
        assert isinstance(func.return_value, NumberLiteral)
        assert func.return_value.value == 5


# ===========================================================================
# Expressions
# ===========================================================================


class TestParseExpressions:
    """Parse expressions with correct precedence and structure."""

    def test_number_literal(self):
        prog = parse("BYTE FUNC F()\nRETURN(42)")
        assert isinstance(prog.declarations[0].return_value, NumberLiteral)
        assert prog.declarations[0].return_value.value == 42

    def test_hex_literal(self):
        prog = parse("BYTE FUNC F()\nRETURN($FF)")
        assert isinstance(prog.declarations[0].return_value, NumberLiteral)
        assert prog.declarations[0].return_value.value == 255

    def test_char_constant(self):
        prog = parse("BYTE FUNC F()\nRETURN('A)")
        val = prog.declarations[0].return_value
        assert isinstance(val, CharConstant)
        assert val.value == 65  # ASCII 'A'

    def test_identifier(self):
        prog = parse("BYTE FUNC F(BYTE x)\nRETURN(x)")
        val = prog.declarations[0].return_value
        assert isinstance(val, Identifier)
        assert val.name == "x"

    def test_binary_add(self):
        prog = parse("BYTE FUNC F(BYTE a, BYTE b)\nRETURN(a + b)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "+"
        assert isinstance(val.left, Identifier)
        assert isinstance(val.right, Identifier)

    def test_precedence_mul_over_add(self):
        """a + b * c should parse as a + (b * c)."""
        prog = parse("BYTE FUNC F(BYTE a, BYTE b, BYTE c)\nRETURN(a + b * c)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "+"
        assert isinstance(val.right, BinaryOp)
        assert val.right.op == "*"

    def test_precedence_and_over_or(self):
        """a OR b AND c should parse as a OR (b AND c)."""
        prog = parse("BYTE FUNC F(BYTE a, BYTE b, BYTE c)\nRETURN(a OR b AND c)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "or"
        assert isinstance(val.right, BinaryOp)
        assert val.right.op == "and"

    def test_precedence_relational(self):
        """a + 1 > b should parse as (a + 1) > b."""
        prog = parse("BYTE FUNC F(BYTE a, BYTE b)\nRETURN(a + 1 > b)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == ">"
        assert isinstance(val.left, BinaryOp)
        assert val.left.op == "+"

    def test_parenthesized(self):
        """(a + b) * c should parse as (a + b) * c."""
        prog = parse("BYTE FUNC F(BYTE a, BYTE b, BYTE c)\nRETURN((a + b) * c)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "*"
        assert isinstance(val.left, BinaryOp)
        assert val.left.op == "+"

    def test_unary_minus(self):
        prog = parse("BYTE FUNC F(BYTE a)\nRETURN(-a)")
        val = prog.declarations[0].return_value
        assert isinstance(val, UnaryOp)
        assert val.op == "-"

    def test_unary_bitwise_not(self):
        prog = parse("BYTE FUNC F(BYTE a)\nRETURN(%a)")
        val = prog.declarations[0].return_value
        assert isinstance(val, UnaryOp)
        assert val.op == "%"

    def test_function_call_in_expr(self):
        prog = parse("BYTE FUNC Get5()\nRETURN(5)\nBYTE FUNC F()\nRETURN(Get5())")
        func_f = prog.declarations[1]
        val = func_f.return_value
        assert isinstance(val, FunctionCall)
        assert val.name == "get5"
        assert val.arguments == []

    def test_function_call_with_args(self):
        prog = parse(
            "BYTE FUNC Add(BYTE a, BYTE b)\nRETURN(a + b)\n"
            "BYTE FUNC F()\nRETURN(Add(1, 2))"
        )
        func_f = prog.declarations[1]
        val = func_f.return_value
        assert isinstance(val, FunctionCall)
        assert len(val.arguments) == 2

    def test_equality_in_expression(self):
        """= in expression context is equality comparison."""
        prog = parse("BYTE FUNC F(BYTE x)\nRETURN(x = 0)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "="

    def test_mod_operator(self):
        prog = parse("BYTE FUNC F(BYTE a, BYTE b)\nRETURN(a MOD b)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "mod"

    def test_shift_operators(self):
        prog = parse("BYTE FUNC F(BYTE a)\nRETURN(a LSH 2)")
        val = prog.declarations[0].return_value
        assert isinstance(val, BinaryOp)
        assert val.op == "lsh"


# ===========================================================================
# Statements
# ===========================================================================


class TestParseAssignment:
    """Parse assignment statements."""

    def test_simple_assignment(self):
        prog = parse("PROC Main()\n  BYTE x\n  x = 5\nRETURN")
        proc = prog.declarations[0]
        assert len(proc.body) == 1
        stmt = proc.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.target, Identifier)
        assert stmt.target.name == "x"
        assert isinstance(stmt.value, NumberLiteral)

    def test_assignment_with_expr(self):
        prog = parse("PROC Main()\n  BYTE x\n  x = x + 1\nRETURN")
        stmt = prog.declarations[0].body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.value, BinaryOp)


class TestParseProcCall:
    """Parse procedure call statements."""

    def test_no_args(self):
        prog = parse("PROC Foo()\nRETURN\nPROC Main()\n  Foo()\nRETURN")
        main = prog.declarations[1]
        assert len(main.body) == 1
        stmt = main.body[0]
        assert isinstance(stmt, ProcCall)
        assert stmt.name == "foo"
        assert stmt.arguments == []

    def test_with_args(self):
        prog = parse(
            "PROC Foo(BYTE a, BYTE b)\nRETURN\nPROC Main()\n  Foo(1, 2)\nRETURN"
        )
        stmt = prog.declarations[1].body[0]
        assert isinstance(stmt, ProcCall)
        assert len(stmt.arguments) == 2


class TestParseIf:
    """Parse IF/THEN/ELSEIF/ELSE/FI statements."""

    def test_simple_if(self):
        prog = parse("PROC Main()\n  BYTE x\n  IF x > 0 THEN\n    x = 1\n  FI\nRETURN")
        stmt = prog.declarations[0].body[0]
        assert isinstance(stmt, IfStmt)
        assert isinstance(stmt.condition, BinaryOp)
        assert len(stmt.then_body) == 1
        assert stmt.elseif_clauses == []
        assert stmt.else_body is None

    def test_if_else(self):
        prog = parse(
            "PROC Main()\n  BYTE x\n"
            "  IF x > 0 THEN\n    x = 1\n  ELSE\n    x = 0\n  FI\nRETURN"
        )
        stmt = prog.declarations[0].body[0]
        assert isinstance(stmt, IfStmt)
        assert len(stmt.then_body) == 1
        assert stmt.else_body is not None
        assert len(stmt.else_body) == 1

    def test_if_elseif(self):
        prog = parse(
            "PROC Main()\n  BYTE x\n"
            "  IF x > 100 THEN\n    x = 100\n"
            "  ELSEIF x < 0 THEN\n    x = 0\n"
            "  FI\nRETURN"
        )
        stmt = prog.declarations[0].body[0]
        assert isinstance(stmt, IfStmt)
        assert len(stmt.elseif_clauses) == 1
        cond, body = stmt.elseif_clauses[0]
        assert isinstance(cond, BinaryOp)
        assert len(body) == 1


class TestParseWhile:
    """Parse WHILE/DO/OD loops."""

    def test_simple_while(self):
        prog = parse(
            "PROC Main()\n  BYTE x\n  WHILE x > 0\n  DO\n    x = x - 1\n  OD\nRETURN"
        )
        stmt = prog.declarations[0].body[0]
        assert isinstance(stmt, WhileLoop)
        assert isinstance(stmt.condition, BinaryOp)
        assert len(stmt.body) == 1


class TestParseReturn:
    """Parse RETURN statements."""

    def test_proc_return(self):
        """PROC RETURN has no value."""
        prog = parse("PROC Main()\nRETURN")
        proc = prog.declarations[0]
        # PROC's final RETURN is implicit in the structure
        assert isinstance(proc, ProcDecl)

    def test_early_return_in_proc(self):
        prog = parse("PROC Main()\n  BYTE x\n  IF x > 0 THEN\n    RETURN\n  FI\nRETURN")
        if_stmt = prog.declarations[0].body[0]
        assert isinstance(if_stmt.then_body[0], ReturnStmt)
        assert if_stmt.then_body[0].value is None

    def test_func_return_with_value(self):
        prog = parse("BYTE FUNC F(BYTE x)\nRETURN(x)")
        func = prog.declarations[0]
        assert func.return_value is not None
        assert isinstance(func.return_value, Identifier)

    def test_early_return_in_func(self):
        prog = parse(
            "BYTE FUNC Max(BYTE a, BYTE b)\n"
            "  IF a > b THEN\n    RETURN(a)\n  FI\n"
            "RETURN(b)"
        )
        func = prog.declarations[0]
        if_stmt = func.body[0]
        assert isinstance(if_stmt.then_body[0], ReturnStmt)
        assert if_stmt.then_body[0].value is not None


# ===========================================================================
# Full program
# ===========================================================================


class TestParseProgram:
    """Parse complete programs with globals and routines."""

    def test_globals_and_proc(self):
        prog = parse("BYTE count\nCARD total=[0]\nPROC Main()\n  count = 1\nRETURN")
        assert len(prog.declarations) == 3
        assert isinstance(prog.declarations[0], VarDecl)
        assert isinstance(prog.declarations[1], VarDecl)
        assert isinstance(prog.declarations[2], ProcDecl)

    def test_multiple_routines(self):
        prog = parse(
            "PROC Foo()\nRETURN\nBYTE FUNC Bar(BYTE x)\nRETURN(x)\nPROC Main()\nRETURN"
        )
        assert len(prog.declarations) == 3
        assert isinstance(prog.declarations[0], ProcDecl)
        assert isinstance(prog.declarations[1], FuncDecl)
        assert isinstance(prog.declarations[2], ProcDecl)


# ===========================================================================
# Parse errors
# ===========================================================================


class TestParseErrors:
    """Invalid syntax produces ParseError."""

    def test_missing_return(self):
        with pytest.raises(ParseError):
            parse("PROC Main()")

    def test_missing_fi(self):
        with pytest.raises(ParseError):
            parse("PROC Main()\n  IF 1 THEN\n    BYTE x\nRETURN")

    def test_missing_od(self):
        with pytest.raises(ParseError):
            parse("PROC Main()\n  WHILE 1\n  DO\nRETURN")

    def test_missing_rparen(self):
        with pytest.raises(ParseError):
            parse("PROC Main(\nRETURN")


# ===========================================================================
# Pointer declarations and dereference
# ===========================================================================


class TestPointerParsing:
    """POINTER declarations and ^ dereference parse correctly."""

    def test_byte_pointer_decl(self):
        prog = parse("BYTE POINTER bp\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, PointerType)
        assert isinstance(decl.type.base_type, ByteType)
        assert decl.name == "bp"

    def test_card_pointer_decl(self):
        prog = parse("CARD POINTER cp\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, PointerType)
        assert isinstance(decl.type.base_type, CardType)

    def test_int_pointer_decl(self):
        prog = parse("INT POINTER ip\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl.type, PointerType)
        assert isinstance(decl.type.base_type, IntType)

    def test_pointer_param(self):
        """PROC with BYTE POINTER parameter."""
        prog = parse("PROC Inc(BYTE POINTER p)\nRETURN")
        proc = prog.declarations[0]
        assert isinstance(proc, ProcDecl)
        assert isinstance(proc.params[0].type, PointerType)

    def test_dereference_in_expression(self):
        """bp^ in expression context parses as Dereference."""
        prog = parse("BYTE POINTER bp\nPROC Main()\n  BYTE x\n  x = bp^\nRETURN")
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.value, Dereference)
        assert isinstance(stmt.value.operand, Identifier)
        assert stmt.value.operand.name == "bp"

    def test_dereference_as_assignment_target(self):
        """bp^ = 42 parses as AssignmentStmt with Dereference target."""
        prog = parse("BYTE POINTER bp\nPROC Main()\n  bp^ = 42\nRETURN")
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.target, Dereference)
        assert isinstance(stmt.target.operand, Identifier)

    def test_address_of_in_expression(self):
        """@x parses as UnaryOp('@', Identifier)."""
        prog = parse("BYTE x\nBYTE POINTER bp\nPROC Main()\n  bp = @x\nRETURN")
        main = prog.declarations[2]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.value, UnaryOp)
        assert stmt.value.op == "@"


# ===========================================================================
# Array declarations and access
# ===========================================================================


class TestArrayParsing:
    """ARRAY declarations and element access parse correctly."""

    def test_byte_array_decl(self):
        prog = parse("BYTE ARRAY buf(256)\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, ArrayType)
        assert isinstance(decl.type.base_type, ByteType)
        assert decl.type.size == 256

    def test_card_array_decl(self):
        prog = parse("CARD ARRAY tbl(100)\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl.type, ArrayType)
        assert isinstance(decl.type.base_type, CardType)
        assert decl.type.size == 100

    def test_array_read_in_expression(self):
        """buf(i) in expression context becomes ArrayAccess."""
        prog = parse(
            "BYTE ARRAY buf(10)\nPROC Main()\n  BYTE x, i\n  x = buf(i)\nRETURN"
        )
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.value, ArrayAccess)
        assert stmt.value.array_name == "buf"
        assert isinstance(stmt.value.index, Identifier)

    def test_array_write_as_target(self):
        """buf(i) = 42 parses as AssignmentStmt with ArrayAccess target."""
        prog = parse("BYTE ARRAY buf(10)\nPROC Main()\n  BYTE i\n  buf(i) = 42\nRETURN")
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.target, ArrayAccess)
        assert stmt.target.array_name == "buf"

    def test_array_bracket_initializer_byte(self):
        """BYTE ARRAY digits = [0 1 2 3] parses with size and initial_values."""
        prog = parse("BYTE ARRAY digits = [0 1 2 3]\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, ArrayType)
        assert isinstance(decl.type.base_type, ByteType)
        assert decl.type.size == 4
        assert decl.initial_values == [0, 1, 2, 3]

    def test_array_bracket_initializer_card(self):
        """CARD ARRAY tbl = [100 200 300] parses with size 3."""
        prog = parse("CARD ARRAY tbl = [100 200 300]\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert isinstance(decl.type, ArrayType)
        assert isinstance(decl.type.base_type, CardType)
        assert decl.type.size == 3
        assert decl.initial_values == [100, 200, 300]

    def test_array_bracket_initializer_hex(self):
        """BYTE ARRAY data = [$FF $00 $AB] parses hex values correctly."""
        prog = parse("BYTE ARRAY data = [$FF $00 $AB]\nPROC Main()\nRETURN")
        decl = prog.declarations[0]
        assert decl.type.size == 3
        assert decl.initial_values == [255, 0, 171]

    def test_array_string_initializer(self):
        """BYTE ARRAY msg = "Hi" stores length byte then char bytes."""
        prog = parse('BYTE ARRAY msg = "Hi"\nPROC Main()\nRETURN')
        decl = prog.declarations[0]
        assert isinstance(decl, VarDecl)
        assert isinstance(decl.type, ArrayType)
        assert decl.type.size == 3  # length byte + 2 chars
        assert decl.initial_values == [2, 72, 105]  # len=2, 'H'=72, 'i'=105

    def test_array_string_initializer_empty(self):
        """BYTE ARRAY e = "" stores just the zero length byte."""
        prog = parse('BYTE ARRAY e = ""\nPROC Main()\nRETURN')
        decl = prog.declarations[0]
        assert decl.type.size == 1
        assert decl.initial_values == [0]

    def test_array_string_initializer_255_chars_ok(self):
        """BYTE ARRAY of exactly 255 chars passes."""
        s = "X" * 255
        prog = parse(f'BYTE ARRAY msg = "{s}"\nPROC Main()\nRETURN')
        decl = prog.declarations[0]
        assert decl.type.size == 256  # 1 length byte + 255 chars

    def test_array_string_initializer_too_long_error(self):
        """BYTE ARRAY with > 255 char string raises ParseError."""
        s = "X" * 256
        with pytest.raises(ParseError, match="too long"):
            parse(f'BYTE ARRAY msg = "{s}"\nPROC Main()\nRETURN')


# ===========================================================================
# SET directive
# ===========================================================================


class TestParseSetDirective:
    """SET directives parse into Program.directives."""

    def test_set_hex_target_numeric_value(self):
        """SET $FFFE = 42 is stored as a SetDirective."""
        prog = parse("PROC Main()\nRETURN\nSET $FFFE = 42")
        assert len(prog.directives) == 1
        d = prog.directives[0]
        assert isinstance(d, SetDirective)
        assert d.target_addr == 0xFFFE
        assert d.value == 42

    def test_set_decimal_target_zero(self):
        """SET 100 = 0 parses decimal target and numeric value."""
        prog = parse("PROC Main()\nRETURN\nSET 100 = 0")
        assert len(prog.directives) == 1
        d = prog.directives[0]
        assert d.target_addr == 100
        assert d.value == 0

    def test_set_identifier_value(self):
        """SET $FFFE = main stores the identifier as a string."""
        prog = parse("PROC Main()\nRETURN\nSET $FFFE = main")
        assert len(prog.directives) == 1
        d = prog.directives[0]
        assert d.target_addr == 0xFFFE
        assert d.value == "main"

    def test_set_multiple_directives(self):
        """Multiple SET directives all appear in prog.directives."""
        prog = parse("PROC Main()\nRETURN\nSET $FFFE = main\nSET 100 = 0")
        assert len(prog.directives) == 2
        assert prog.directives[0].target_addr == 0xFFFE
        assert prog.directives[1].target_addr == 100

    def test_set_does_not_appear_in_declarations(self):
        """SET directive is not added to prog.declarations."""
        prog = parse("PROC Main()\nRETURN\nSET $FFFE = main")
        # Only the PROC is a declaration
        assert len(prog.declarations) == 1
        assert isinstance(prog.declarations[0], ProcDecl)


# ===========================================================================
# String literals in expressions
# ===========================================================================


class TestStringLiteralExpr:
    """String constants in expression context parse as StringLiteral."""

    def test_string_literal_in_assignment(self):
        """p = "Hello" parses RHS as StringLiteral."""
        prog = parse('BYTE POINTER p\nPROC Main()\n  p = "Hello"\nRETURN')
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, AssignmentStmt)
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == "Hello"

    def test_string_literal_empty(self):
        """p = "" parses as StringLiteral with empty value."""
        prog = parse('BYTE POINTER p\nPROC Main()\n  p = ""\nRETURN')
        stmt = prog.declarations[1].body[0]
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == ""

    def test_string_literal_with_escaped_quote(self):
        # Action! escapes a literal quote as "" inside a string.
        # "say ""hi""" unescapes to: say "hi"
        prog = parse('BYTE POINTER p\nPROC Main()\n  p = "say ""hi"""\nRETURN')
        stmt = prog.declarations[1].body[0]
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == 'say "hi"'

    def test_string_literal_as_argument(self):
        """f("msg") passes string literal as argument."""
        prog = parse(
            'PROC Print(BYTE POINTER s)\nRETURN\nPROC Main()\n  Print("msg")\nRETURN'
        )
        main = prog.declarations[1]
        stmt = main.body[0]
        assert isinstance(stmt, ProcCall)
        assert isinstance(stmt.arguments[0], StringLiteral)
        assert stmt.arguments[0].value == "msg"
