"""Abstract Syntax Tree node definitions for SK02-C."""

from dataclasses import dataclass, field
from typing import Optional


# Types
@dataclass
class BasicType:
    """Basic type: char, int, void."""

    name: str  # "char", "int", "void"
    line: int
    column: int


@dataclass
class PointerType:
    """Pointer type."""

    base_type: "BasicType | PointerType | ArrayType"
    line: int
    column: int


@dataclass
class ArrayType:
    """Array type."""

    base_type: "BasicType | PointerType"
    size: Optional[int]  # None for unsized arrays
    line: int
    column: int


# Type alias for convenience
Type = BasicType | PointerType | ArrayType


# Expressions
@dataclass
class NumberLiteral:
    """Numeric literal."""

    value: int
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class CharLiteral:
    """Character literal."""

    value: str  # The character
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class StringLiteral:
    """String literal."""

    value: str
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class Identifier:
    """Variable or function name."""

    name: str
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class BinaryOp:
    """Binary operation."""

    op: str  # "+", "-", "*", "/", etc.
    left: "Expression"
    right: "Expression"
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class UnaryOp:
    """Unary operation."""

    op: str  # "-", "!", "~", "*", "&", "++", "--"
    operand: "Expression"
    postfix: bool  # True for postfix ++/--
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class Assignment:
    """Assignment expression."""

    target: "Expression"
    op: str  # "=", "+=", "-=", etc.
    value: "Expression"
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class FunctionCall:
    """Function call."""

    function: str
    arguments: list["Expression"]
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


@dataclass
class ArrayAccess:
    """Array subscript."""

    array: "Expression"
    index: "Expression"
    line: int
    column: int
    resolved_type: Optional["Type"] = field(default=None, compare=False)


# Type alias for expressions
Expression = (
    NumberLiteral
    | CharLiteral
    | StringLiteral
    | Identifier
    | BinaryOp
    | UnaryOp
    | Assignment
    | FunctionCall
    | ArrayAccess
)


# Statements
@dataclass
class ExpressionStatement:
    """Expression as statement."""

    expression: Optional[Expression]  # None for empty statement
    line: int
    column: int


@dataclass
class CompoundStatement:
    """Block of statements."""

    statements: list["Statement"]
    line: int
    column: int


@dataclass
class ReturnStatement:
    """Return statement."""

    value: Optional[Expression]
    line: int
    column: int


@dataclass
class IfStatement:
    """If statement."""

    condition: Expression
    then_stmt: "Statement"
    else_stmt: Optional["Statement"]
    line: int
    column: int


@dataclass
class WhileStatement:
    """While loop."""

    condition: Expression
    body: "Statement"
    line: int
    column: int


@dataclass
class ForStatement:
    """For loop."""

    init: Optional[Expression]
    condition: Optional[Expression]
    increment: Optional[Expression]
    body: "Statement"
    line: int
    column: int


@dataclass
class BreakStatement:
    """Break statement."""

    line: int
    column: int


@dataclass
class ContinueStatement:
    """Continue statement."""

    line: int
    column: int


# Declarations
@dataclass
class VariableDeclaration:
    """Variable declaration."""

    type: Type
    name: str
    initializer: Optional[Expression]
    is_static: bool
    is_register: bool
    is_const: bool
    line: int
    column: int


@dataclass
class Parameter:
    """Function parameter."""

    type: Type
    name: str
    line: int
    column: int


@dataclass
class FunctionDeclaration:
    """Function declaration/definition."""

    return_type: Type
    name: str
    parameters: list[Parameter]
    body: Optional[CompoundStatement]  # None for declarations
    line: int
    column: int


# Type alias for statements
Statement = (
    ExpressionStatement
    | CompoundStatement
    | ReturnStatement
    | IfStatement
    | WhileStatement
    | ForStatement
    | BreakStatement
    | ContinueStatement
    | VariableDeclaration
)


@dataclass
class Program:
    """Top-level program."""

    declarations: list[VariableDeclaration | FunctionDeclaration]
    line: int
    column: int
