"""Semantic analysis / type checker for SK02-C.

Walks the AST produced by the parser and annotates every expression node
with its ``resolved_type`` field.  Errors are raised early — before code
generation — with precise source locations.

Checks performed:
- All referenced variables are declared in scope.
- Function calls reference known functions and pass the right argument count.
- Dereference (*) and address-of (&) are applied to the right kinds of values.

Type *promotion* is deliberately minimal (matching the limited SK02-C type
system): the checker resolves to the *left-operand* type for binary ops and
produces ``BasicType("int")`` for boolean results (comparisons, logical ops).
"""

from .ast_nodes import (
    ArrayAccess,
    ArrayType,
    Assignment,
    BasicType,
    BinaryOp,
    BreakStatement,
    CharLiteral,
    CompoundStatement,
    ContinueStatement,
    Expression,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    NumberLiteral,
    Parameter,
    PointerType,
    Program,
    ReturnStatement,
    Statement,
    StringLiteral,
    Type,
    UnaryOp,
    VariableDeclaration,
    WhileStatement,
)


class SemanticError(Exception):
    """Semantic / type error with source location."""

    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Semantic error at {line}:{column}: {message}")
        self.line = line
        self.column = column


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHAR_TYPE = BasicType("char", 0, 0)
_INT_TYPE = BasicType("int", 0, 0)
_BOOL_TYPE = BasicType("char", 0, 0)  # booleans fit in char (0 or 1)


def _type_size(typ: Type) -> int:
    """Return byte size of a type (mirrors CodeGenerator.get_type_size)."""
    if isinstance(typ, BasicType):
        if typ.name in ("char", "uint8", "int8"):
            return 1
        if typ.name in ("int", "uint16", "int16"):
            return 2
        return 0  # void
    if isinstance(typ, PointerType):
        return 2
    if isinstance(typ, ArrayType):
        if typ.size is None:
            return 0
        return _type_size(typ.base_type) * typ.size
    return 0


# ---------------------------------------------------------------------------
# Scope / symbol table
# ---------------------------------------------------------------------------

class _Scope:
    """Simple two-level scope: globals + one function-local frame."""

    def __init__(self):
        self._globals: dict[str, Type] = {}
        self._locals: dict[str, Type] = {}

    def declare_global(self, name: str, typ: Type) -> None:
        self._globals[name] = typ

    def declare_local(self, name: str, typ: Type) -> None:
        self._locals[name] = typ

    def resolve(self, name: str) -> Type | None:
        return self._locals.get(name) or self._globals.get(name)

    def enter_function(self) -> None:
        self._locals = {}

    def exit_function(self) -> None:
        self._locals = {}


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

class TypeChecker:
    """Annotates AST expression nodes with resolved_type."""

    def __init__(self):
        self._scope = _Scope()
        self._function_signatures: dict[str, list[Parameter]] = {}
        self._current_return_type: Type | None = None


    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------

    def _check_function(self, func: FunctionDeclaration) -> None:
        self._scope.enter_function()
        self._current_return_type = func.return_type

        # Register parameters in local scope.
        for param in func.parameters:
            self._scope.declare_local(param.name, param.type)

        if func.body:
            self._check_statement(func.body)

        self._scope.exit_function()
        self._current_return_type = None

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _check_statement(self, stmt: Statement) -> None:
        if isinstance(stmt, CompoundStatement):
            for s in stmt.statements:
                self._check_statement(s)

        elif isinstance(stmt, ExpressionStatement):
            if stmt.expression:
                self._check_expr(stmt.expression)

        elif isinstance(stmt, ReturnStatement):
            if stmt.value:
                self._check_expr(stmt.value)

        elif isinstance(stmt, IfStatement):
            self._check_expr(stmt.condition)
            self._check_statement(stmt.then_stmt)
            if stmt.else_stmt:
                self._check_statement(stmt.else_stmt)

        elif isinstance(stmt, WhileStatement):
            self._check_expr(stmt.condition)
            self._check_statement(stmt.body)

        elif isinstance(stmt, ForStatement):
            if stmt.init:
                self._check_expr(stmt.init)
            if stmt.condition:
                self._check_expr(stmt.condition)
            if stmt.increment:
                self._check_expr(stmt.increment)
            self._check_statement(stmt.body)

        elif isinstance(stmt, VariableDeclaration):
            self._scope.declare_local(stmt.name, stmt.type)
            if stmt.initializer:
                self._check_expr(stmt.initializer)

        elif isinstance(stmt, (BreakStatement, ContinueStatement)):
            pass  # no type checking needed

        else:
            raise SemanticError(
                f"Unknown statement type: {type(stmt).__name__}", 0, 0
            )

    # ------------------------------------------------------------------
    # Expressions  (mutates node.resolved_type in-place)
    # ------------------------------------------------------------------

    def _check_expr(self, expr: Expression) -> Type:
        """Type-check *expr*, set its resolved_type, and return the type."""
        if isinstance(expr, NumberLiteral):
            # Small values default to char; larger values to int.
            typ = _CHAR_TYPE if 0 <= expr.value <= 255 else _INT_TYPE
            expr.resolved_type = typ
            return typ

        if isinstance(expr, CharLiteral):
            expr.resolved_type = _CHAR_TYPE
            return _CHAR_TYPE

        if isinstance(expr, StringLiteral):
            typ = PointerType(_CHAR_TYPE, expr.line, expr.column)
            expr.resolved_type = typ
            return typ

        if isinstance(expr, Identifier):
            typ = self._scope.resolve(expr.name)
            if typ is None:
                raise SemanticError(
                    f"Undefined variable: {expr.name}", expr.line, expr.column
                )
            expr.resolved_type = typ
            return typ

        if isinstance(expr, BinaryOp):
            return self._check_binary(expr)

        if isinstance(expr, UnaryOp):
            return self._check_unary(expr)

        if isinstance(expr, Assignment):
            return self._check_assignment(expr)

        if isinstance(expr, FunctionCall):
            return self._check_call(expr)

        if isinstance(expr, ArrayAccess):
            arr_type = self._check_expr(expr.array)
            self._check_expr(expr.index)
            if isinstance(arr_type, ArrayType):
                elem = arr_type.base_type
            elif isinstance(arr_type, PointerType):
                elem = arr_type.base_type
            else:
                raise SemanticError(
                    "Subscript applied to non-array/pointer type",
                    expr.line,
                    expr.column,
                )
            expr.resolved_type = elem
            return elem

        raise SemanticError(
            f"Unknown expression type: {type(expr).__name__}", 0, 0
        )

    def _check_binary(self, expr: BinaryOp) -> Type:
        left_type = self._check_expr(expr.left)
        right_type = self._check_expr(expr.right)

        boolean_ops = {"==", "!=", "<", ">", "<=", ">=", "&&", "||"}
        if expr.op in boolean_ops:
            expr.resolved_type = _BOOL_TYPE
            return _BOOL_TYPE

        # Arithmetic / bitwise: use left-operand type as result type.
        result = left_type
        expr.resolved_type = result
        return result

    def _check_unary(self, expr: UnaryOp) -> Type:
        operand_type = self._check_expr(expr.operand)

        if expr.op == "&":
            if not isinstance(expr.operand, Identifier):
                raise SemanticError(
                    "Address-of requires a variable", expr.line, expr.column
                )
            typ = PointerType(operand_type, expr.line, expr.column)
            expr.resolved_type = typ
            return typ

        if expr.op == "*":
            if not isinstance(operand_type, PointerType):
                raise SemanticError(
                    "Dereference of non-pointer type", expr.line, expr.column
                )
            typ = operand_type.base_type
            expr.resolved_type = typ
            return typ

        if expr.op in ("++", "--"):
            expr.resolved_type = operand_type
            return operand_type

        # "-", "!", "~"
        expr.resolved_type = operand_type
        return operand_type

    def _check_assignment(self, expr: Assignment) -> Type:
        target_type = self._check_expr(expr.target)
        self._check_expr(expr.value)
        expr.resolved_type = target_type
        return target_type

    def _check_call(self, expr: FunctionCall) -> Type:
        params = self._function_signatures.get(expr.function)
        if params is None:
            raise SemanticError(
                f"Call to undeclared function: {expr.function}",
                expr.line,
                expr.column,
            )

        if len(expr.arguments) != len(params):
            raise SemanticError(
                f"Function '{expr.function}' expects {len(params)} argument(s),"
                f" got {len(expr.arguments)}",
                expr.line,
                expr.column,
            )

        for arg in expr.arguments:
            self._check_expr(arg)

        # Return type is the function's declared return type.
        # We need to look it up — store it alongside params.
        # For now, return type is encoded in the FunctionDeclaration; we
        # reconstruct a best-guess from the function signatures dict being
        # populated later.  Use _return_types dict populated in check().
        typ = self._return_types.get(expr.function, _INT_TYPE)
        expr.resolved_type = typ
        return typ

    def check(self, program: Program) -> None:
        """Entry point.  Mutates AST nodes in-place."""
        # Collect return types alongside signatures.
        self._return_types: dict[str, Type] = {}
        for decl in program.declarations:
            if isinstance(decl, VariableDeclaration):
                self._scope.declare_global(decl.name, decl.type)
            elif isinstance(decl, FunctionDeclaration):
                self._function_signatures[decl.name] = decl.parameters
                self._return_types[decl.name] = decl.return_type

        for decl in program.declarations:
            if isinstance(decl, FunctionDeclaration):
                self._check_function(decl)
