"""Call graph analysis for the SK-02 Action! compiler.

Builds a directed graph of routine-calls-routine relationships.
Used for: recursion detection (illegal in Action!), and future
local variable overlay optimization.
"""

from .ast_nodes import (
    AssignmentStmt,
    BinaryOp,
    DoLoop,
    Expression,
    ForLoop,
    FuncDecl,
    FunctionCall,
    IfStmt,
    ProcCall,
    ProcDecl,
    Program,
    ReturnStmt,
    Statement,
    UnaryOp,
    UntilLoop,
    WhileLoop,
)
from .type_checker import _INTRINSIC_NAMES


class RecursionError(Exception):
    """Raised when illegal recursion is detected."""

    pass


class CallGraph:
    """Directed call graph for all routines in the program."""

    def __init__(self, program: Program):
        self._edges: dict[str, set[str]] = {}
        self._build(program)

    def _build(self, program: Program) -> None:
        for decl in program.declarations:
            if isinstance(decl, ProcDecl):
                calls = set()
                for stmt in decl.body:
                    self._collect_calls_stmt(stmt, calls)
                self._edges[decl.name] = calls
            elif isinstance(decl, FuncDecl):
                calls = set()
                for stmt in decl.body:
                    self._collect_calls_stmt(stmt, calls)
                self._collect_calls_expr(decl.return_value, calls)
                self._edges[decl.name] = calls

    def _collect_calls_stmt(self, stmt: Statement, calls: set[str]) -> None:
        if isinstance(stmt, ProcCall):
            if stmt.name not in _INTRINSIC_NAMES:
                calls.add(stmt.name)
            for arg in stmt.arguments:
                self._collect_calls_expr(arg, calls)
        elif isinstance(stmt, AssignmentStmt):
            self._collect_calls_expr(stmt.value, calls)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                self._collect_calls_expr(stmt.value, calls)
        elif isinstance(stmt, IfStmt):
            self._collect_calls_expr(stmt.condition, calls)
            for s in stmt.then_body:
                self._collect_calls_stmt(s, calls)
            for cond, body in stmt.elseif_clauses:
                self._collect_calls_expr(cond, calls)
                for s in body:
                    self._collect_calls_stmt(s, calls)
            if stmt.else_body:
                for s in stmt.else_body:
                    self._collect_calls_stmt(s, calls)
        elif isinstance(stmt, (WhileLoop, UntilLoop)):
            self._collect_calls_expr(stmt.condition, calls)
            for s in stmt.body:
                self._collect_calls_stmt(s, calls)
        elif isinstance(stmt, DoLoop):
            for s in stmt.body:
                self._collect_calls_stmt(s, calls)
        elif isinstance(stmt, ForLoop):
            self._collect_calls_expr(stmt.start, calls)
            self._collect_calls_expr(stmt.limit, calls)
            if stmt.step:
                self._collect_calls_expr(stmt.step, calls)
            for s in stmt.body:
                self._collect_calls_stmt(s, calls)

    def _collect_calls_expr(self, expr: Expression, calls: set[str]) -> None:
        if isinstance(expr, FunctionCall):
            if expr.name not in _INTRINSIC_NAMES:
                calls.add(expr.name)
            for arg in expr.arguments:
                self._collect_calls_expr(arg, calls)
        elif isinstance(expr, BinaryOp):
            self._collect_calls_expr(expr.left, calls)
            self._collect_calls_expr(expr.right, calls)
        elif isinstance(expr, UnaryOp):
            self._collect_calls_expr(expr.operand, calls)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def callees(self, name: str) -> set[str]:
        """Return the set of routines directly called by `name`."""
        return self._edges.get(name, set())

    def transitive_callees(self, name: str) -> set[str]:
        """Return all routines reachable from `name` (not including itself)."""
        visited: set[str] = set()
        stack = list(self._edges.get(name, set()))
        while stack:
            callee = stack.pop()
            if callee not in visited:
                visited.add(callee)
                stack.extend(self._edges.get(callee, set()) - visited)
        return visited

    def check_no_recursion(self) -> None:
        """Raise RecursionError if any routine calls itself directly or indirectly."""
        for name in self._edges:
            if name in self._edges[name]:
                raise RecursionError(
                    f"Direct recursion detected: {name!r} calls itself"
                )
            if name in self.transitive_callees(name):
                raise RecursionError(
                    f"Recursion detected: {name!r} is reachable from itself"
                )

    def can_overlap(self, a: str, b: str) -> bool:
        """True if neither routine is reachable from the other."""
        return b not in self.transitive_callees(a) and a not in self.transitive_callees(
            b
        )
