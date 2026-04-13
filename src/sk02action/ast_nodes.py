"""Abstract Syntax Tree node definitions for SK-02 Action!."""

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class ByteType:
    """BYTE or CHAR type (8-bit unsigned)."""

    line: int
    column: int


@dataclass
class CardType:
    """CARD type (16-bit unsigned)."""

    line: int
    column: int


@dataclass
class IntType:
    """INT type (16-bit signed)."""

    line: int
    column: int


@dataclass
class PointerType:
    """BYTE/CARD/INT POINTER type (holds a 16-bit address)."""

    base_type: "Type"
    line: int
    column: int


@dataclass
class ArrayType:
    """BYTE/CARD/INT ARRAY type (base address + element count)."""

    base_type: "Type"
    size: int  # number of elements
    line: int
    column: int


Type = ByteType | CardType | IntType | PointerType | ArrayType


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass
class NumberLiteral:
    """Numeric literal (decimal or hex)."""

    value: int
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class CharConstant:
    """Character constant ('A → 65)."""

    value: int  # ASCII code
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class Identifier:
    """Variable or function name reference."""

    name: str
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class BinaryOp:
    """Binary operation."""

    op: str  # "+", "-", "*", "/", "mod", "lsh", "rsh", "and", "or", "xor",
    # "=", "<>", "<", ">", "<=", ">="
    left: "Expression"
    right: "Expression"
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class UnaryOp:
    """Unary operation."""

    op: str  # "-" (negate), "%" (bitwise NOT), "@" (address-of)
    operand: "Expression"
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class FunctionCall:
    """Function call in expression context."""

    name: str
    arguments: list["Expression"]
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class Dereference:
    """Pointer dereference: ptr^."""

    operand: "Expression"
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class ArrayAccess:
    """Array element access: arr(index)."""

    array_name: str
    index: "Expression"
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


@dataclass
class StringLiteral:
    """String constant in expression context: "Hello" → anonymous BYTE ARRAY address."""

    value: str  # decoded string (no surrounding quotes, "" unescaped)
    line: int
    column: int
    resolved_type: Optional[Type] = field(default=None, compare=False)


Expression = (
    NumberLiteral
    | CharConstant
    | Identifier
    | BinaryOp
    | UnaryOp
    | FunctionCall
    | Dereference
    | ArrayAccess
    | StringLiteral
)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass
class AssignmentStmt:
    """Assignment: target = value."""

    target: Expression
    value: Expression
    line: int
    column: int


@dataclass
class ProcCall:
    """Procedure call statement."""

    name: str
    arguments: list[Expression]
    line: int
    column: int


@dataclass
class ReturnStmt:
    """Early RETURN statement (within IF/loop body)."""

    value: Optional[Expression]  # None for PROC, expr for FUNC
    line: int
    column: int


@dataclass
class IfStmt:
    """IF/THEN/ELSEIF/ELSE/FI."""

    condition: Expression
    then_body: list["Statement"]
    elseif_clauses: list[tuple[Expression, list["Statement"]]]
    else_body: Optional[list["Statement"]]
    line: int
    column: int


@dataclass
class WhileLoop:
    """WHILE condition DO stmts OD."""

    condition: Expression
    body: list["Statement"]
    line: int
    column: int


@dataclass
class DoLoop:
    """DO stmts OD (unconditional loop)."""

    body: list["Statement"]
    line: int
    column: int


@dataclass
class UntilLoop:
    """UNTIL condition DO stmts OD."""

    condition: Expression
    body: list["Statement"]
    line: int
    column: int


@dataclass
class ForLoop:
    """FOR ident = start TO limit [STEP inc] DO stmts OD."""

    var_name: str
    start: Expression
    limit: Expression
    step: Optional[Expression]
    body: list["Statement"]
    line: int
    column: int


@dataclass
class ExitStmt:
    """EXIT statement (break from innermost loop)."""

    line: int
    column: int


Statement = (
    AssignmentStmt
    | ProcCall
    | ReturnStmt
    | IfStmt
    | WhileLoop
    | DoLoop
    | UntilLoop
    | ForLoop
    | ExitStmt
)


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


@dataclass
class VarDecl:
    """Variable declaration."""

    type: Type
    name: str
    address: Optional[int]  # =addr placement
    initial_value: Optional[int]  # =[value] initializer for scalars
    line: int
    column: int
    initial_values: Optional[list[int]] = field(default=None)  # array initializer


@dataclass
class Parameter:
    """Routine parameter."""

    type: Type
    name: str
    line: int
    column: int


@dataclass
class ProcDecl:
    """PROC declaration."""

    name: str
    params: list[Parameter]
    locals: list[VarDecl]
    body: list[Statement]
    line: int
    column: int


@dataclass
class FuncDecl:
    """FUNC declaration with return type."""

    return_type: Type
    name: str
    params: list[Parameter]
    locals: list[VarDecl]
    body: list[Statement]
    return_value: Expression  # mandatory final RETURN(expr)
    line: int
    column: int


Declaration = VarDecl | ProcDecl | FuncDecl


# ---------------------------------------------------------------------------
# Directives
# ---------------------------------------------------------------------------


@dataclass
class SetDirective:
    """SET target_addr = value — pokes bytes into the output ROM at compile time."""

    target_addr: int  # address to write to (numeric constant)
    value: int | str  # int literal or identifier name (resolved to label at codegen)
    line: int
    column: int


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


@dataclass
class Program:
    """Top-level program."""

    declarations: list[Declaration]
    line: int
    column: int
    directives: list[SetDirective] = field(default_factory=list)
