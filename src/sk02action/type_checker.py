"""Type checker for the SK-02 Action! compiler.

Walks the AST, annotates expression nodes with resolved_type,
and checks for semantic errors (undeclared names, wrong arg counts).
"""

from .ast_nodes import (
    ArrayAccess,
    ArrayType,
    AssignmentStmt,
    BinaryOp,
    ByteType,
    CardType,
    CharConstant,
    Dereference,
    DoLoop,
    ExitStmt,
    Expression,
    ForLoop,
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
    Statement,
    Type,
    UnaryOp,
    UntilLoop,
    VarDecl,
    WhileLoop,
)
from .symbol_table import SymbolTable


class SemanticError(Exception):
    """Semantic analysis error."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        super().__init__(f"Semantic error at {line}:{column}: {message}")
        self.line = line
        self.column = column


def _type_size(t: Type) -> int:
    if isinstance(t, ByteType):
        return 1
    if isinstance(t, ArrayType):
        elem_size = 1 if isinstance(t.base_type, ByteType) else 2
        return elem_size * t.size
    return 2  # CardType, IntType, PointerType


def _is_16bit(t: Type) -> bool:
    return isinstance(t, (CardType, IntType, PointerType))


def _widen(a: Type, b: Type) -> Type:
    """Determine result type when combining two operand types."""
    if isinstance(a, ByteType) and isinstance(b, ByteType):
        return a
    # At least one is 16-bit. INT wins if either is INT.
    if isinstance(a, IntType) or isinstance(b, IntType):
        return a if isinstance(a, IntType) else b
    # Otherwise CARD
    return a if isinstance(a, CardType) else b


class TypeChecker:
    """Annotates AST with resolved types and checks semantics."""

    def __init__(self):
        self._st = SymbolTable()

    def check(self, program: Program) -> None:
        """Type-check the entire program."""
        # First pass: register all top-level declarations
        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                self._declare_var(decl)
            elif isinstance(decl, ProcDecl):
                self._st.declare_func(
                    decl.name,
                    params=[{"name": p.name, "type": p.type} for p in decl.params],
                    return_type=None,
                )
            elif isinstance(decl, FuncDecl):
                self._st.declare_func(
                    decl.name,
                    params=[{"name": p.name, "type": p.type} for p in decl.params],
                    return_type=decl.return_type,
                )

        # Second pass: check routine bodies
        for decl in program.declarations:
            if isinstance(decl, ProcDecl):
                self._check_proc(decl)
            elif isinstance(decl, FuncDecl):
                self._check_func(decl)

    def _declare_var(self, decl: VarDecl) -> None:
        self._st.declare_var(
            decl.name,
            decl.type,
            size=_type_size(decl.type),
            address=decl.address,
            initial_value=decl.initial_value,
        )

    def _check_proc(self, proc: ProcDecl) -> None:
        self._st.enter_scope(proc.name)
        self._register_params(proc.params)
        for local in proc.locals:
            self._declare_var(local)
        for stmt in proc.body:
            self._check_stmt(stmt)
        self._st.exit_scope()

    def _check_func(self, func: FuncDecl) -> None:
        self._st.enter_scope(func.name)
        self._register_params(func.params)
        for local in func.locals:
            self._declare_var(local)
        for stmt in func.body:
            self._check_stmt(stmt)
        self._check_expr(func.return_value)
        self._st.exit_scope()

    def _register_params(self, params: list[Parameter]) -> None:
        for p in params:
            self._st.declare_var(p.name, p.type, size=_type_size(p.type))

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _check_stmt(self, stmt: Statement) -> None:
        if isinstance(stmt, AssignmentStmt):
            self._check_expr(stmt.target)
            self._check_expr(stmt.value)
        elif isinstance(stmt, ProcCall):
            self._check_call(stmt.name, stmt.arguments, stmt.line, stmt.column)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                self._check_expr(stmt.value)
        elif isinstance(stmt, IfStmt):
            self._check_expr(stmt.condition)
            for s in stmt.then_body:
                self._check_stmt(s)
            for cond, body in stmt.elseif_clauses:
                self._check_expr(cond)
                for s in body:
                    self._check_stmt(s)
            if stmt.else_body:
                for s in stmt.else_body:
                    self._check_stmt(s)
        elif isinstance(stmt, WhileLoop):
            self._check_expr(stmt.condition)
            for s in stmt.body:
                self._check_stmt(s)
        elif isinstance(stmt, DoLoop):
            for s in stmt.body:
                self._check_stmt(s)
        elif isinstance(stmt, UntilLoop):
            self._check_expr(stmt.condition)
            for s in stmt.body:
                self._check_stmt(s)
        elif isinstance(stmt, ForLoop):
            self._check_expr(stmt.start)
            self._check_expr(stmt.limit)
            if stmt.step:
                self._check_expr(stmt.step)
            for s in stmt.body:
                self._check_stmt(s)
        elif isinstance(stmt, ExitStmt):
            pass

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _check_expr(self, expr: Expression) -> Type:
        if isinstance(expr, NumberLiteral):
            if expr.value < 0:
                expr.resolved_type = IntType(expr.line, expr.column)
            elif expr.value < 256:
                expr.resolved_type = ByteType(expr.line, expr.column)
            else:
                expr.resolved_type = CardType(expr.line, expr.column)
            return expr.resolved_type

        elif isinstance(expr, CharConstant):
            expr.resolved_type = ByteType(expr.line, expr.column)
            return expr.resolved_type

        elif isinstance(expr, Identifier):
            info = self._st.resolve(expr.name)
            if info is None:
                raise SemanticError(
                    f"Undeclared variable: {expr.name!r}",
                    expr.line,
                    expr.column,
                )
            expr.resolved_type = info["type"]
            return expr.resolved_type

        elif isinstance(expr, BinaryOp):
            left_type = self._check_expr(expr.left)
            right_type = self._check_expr(expr.right)
            if expr.op in ("=", "<>", "<", ">", "<=", ">="):
                expr.resolved_type = ByteType(expr.line, expr.column)
            else:
                expr.resolved_type = _widen(left_type, right_type)
            return expr.resolved_type

        elif isinstance(expr, UnaryOp):
            operand_type = self._check_expr(expr.operand)
            if expr.op == "-":
                # Unary minus produces INT (negative values need signed type)
                expr.resolved_type = IntType(expr.line, expr.column)
            elif expr.op == "@":
                # Address-of: produces a pointer to the operand's type
                expr.resolved_type = PointerType(
                    operand_type, expr.line, expr.column
                )
            else:
                expr.resolved_type = operand_type
            return expr.resolved_type

        elif isinstance(expr, ArrayAccess):
            info = self._st.resolve(expr.array_name)
            if info is None:
                raise SemanticError(
                    f"Undeclared array: {expr.array_name!r}",
                    expr.line,
                    expr.column,
                )
            arr_type = info["type"]
            if not isinstance(arr_type, ArrayType):
                raise SemanticError(
                    f"{expr.array_name!r} is not an array",
                    expr.line,
                    expr.column,
                )
            self._check_expr(expr.index)
            expr.resolved_type = arr_type.base_type
            return expr.resolved_type

        elif isinstance(expr, Dereference):
            ptr_type = self._check_expr(expr.operand)
            if not isinstance(ptr_type, PointerType):
                raise SemanticError(
                    "Cannot dereference non-pointer type",
                    expr.line,
                    expr.column,
                )
            expr.resolved_type = ptr_type.base_type
            return expr.resolved_type

        elif isinstance(expr, FunctionCall):
            return self._check_func_call(expr)

        raise SemanticError(
            f"Unknown expression type: {type(expr).__name__}",
            getattr(expr, "line", 0),
            getattr(expr, "column", 0),
        )

    def _check_call(
        self, name: str, args: list[Expression], line: int, column: int
    ) -> None:
        """Check a procedure/function call (statement context)."""
        func_info = self._st.resolve_func(name)
        if func_info is None:
            raise SemanticError(f"Undeclared procedure: {name!r}", line, column)
        expected = len(func_info["params"])
        actual = len(args)
        if actual != expected:
            raise SemanticError(
                f"{name!r} expects {expected} argument(s), got {actual}",
                line,
                column,
            )
        for arg in args:
            self._check_expr(arg)

    def _check_func_call(self, expr: FunctionCall) -> Type:
        """Check a function call in expression context."""
        func_info = self._st.resolve_func(expr.name)
        if func_info is None:
            raise SemanticError(
                f"Undeclared function: {expr.name!r}",
                expr.line,
                expr.column,
            )
        expected = len(func_info["params"])
        actual = len(expr.arguments)
        if actual != expected:
            raise SemanticError(
                f"{expr.name!r} expects {expected} argument(s), got {actual}",
                expr.line,
                expr.column,
            )
        for arg in expr.arguments:
            self._check_expr(arg)
        ret_type = func_info["return_type"]
        if ret_type is None:
            # PROC called in expression context — default to BYTE
            expr.resolved_type = ByteType(expr.line, expr.column)
        else:
            expr.resolved_type = ret_type
        return expr.resolved_type
