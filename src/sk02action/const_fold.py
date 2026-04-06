"""Constant folding pass for the SK-02 Action! compiler.

Walks the AST after type checking and replaces BinaryOp/UnaryOp nodes
where all operands are constants with a single NumberLiteral.
Respects 8-bit vs 16-bit overflow masking based on resolved_type.
"""

from .ast_nodes import (
    AssignmentStmt,
    BinaryOp,
    ByteType,
    CharConstant,
    DoLoop,
    Expression,
    ForLoop,
    FuncDecl,
    FunctionCall,
    Identifier,
    IfStmt,
    IntType,
    NumberLiteral,
    ProcCall,
    ProcDecl,
    Program,
    ReturnStmt,
    Statement,
    Type,
    UnaryOp,
    UntilLoop,
    WhileLoop,
)


def _is_constant(expr: Expression) -> bool:
    return isinstance(expr, (NumberLiteral, CharConstant))


def _const_value(expr: Expression) -> int:
    if isinstance(expr, NumberLiteral):
        return expr.value
    if isinstance(expr, CharConstant):
        return expr.value
    raise ValueError(f"Not a constant: {type(expr).__name__}")


def _mask(value: int, typ: Type) -> int:
    """Mask value to fit the type width, preserving sign for INT."""
    if isinstance(typ, ByteType):
        return value & 0xFF
    if isinstance(typ, IntType):
        # Signed 16-bit: wrap to -32768..32767
        value = value & 0xFFFF
        if value >= 0x8000:
            value -= 0x10000
        return value
    return value & 0xFFFF


class ConstantFolder:
    """Folds constant expressions in the AST in-place."""

    def fold(self, program: Program) -> None:
        for decl in program.declarations:
            if isinstance(decl, ProcDecl):
                decl.body = [self._fold_stmt(s) for s in decl.body]
            elif isinstance(decl, FuncDecl):
                decl.body = [self._fold_stmt(s) for s in decl.body]
                decl.return_value = self._fold_expr(decl.return_value)

    def _fold_stmt(self, stmt: Statement) -> Statement:
        if isinstance(stmt, AssignmentStmt):
            stmt.value = self._fold_expr(stmt.value)
        elif isinstance(stmt, ProcCall):
            stmt.arguments = [self._fold_expr(a) for a in stmt.arguments]
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                stmt.value = self._fold_expr(stmt.value)
        elif isinstance(stmt, IfStmt):
            stmt.condition = self._fold_expr(stmt.condition)
            stmt.then_body = [self._fold_stmt(s) for s in stmt.then_body]
            stmt.elseif_clauses = [
                (self._fold_expr(c), [self._fold_stmt(s) for s in body])
                for c, body in stmt.elseif_clauses
            ]
            if stmt.else_body:
                stmt.else_body = [self._fold_stmt(s) for s in stmt.else_body]
        elif isinstance(stmt, WhileLoop):
            stmt.condition = self._fold_expr(stmt.condition)
            stmt.body = [self._fold_stmt(s) for s in stmt.body]
        elif isinstance(stmt, DoLoop):
            stmt.body = [self._fold_stmt(s) for s in stmt.body]
        elif isinstance(stmt, UntilLoop):
            stmt.condition = self._fold_expr(stmt.condition)
            stmt.body = [self._fold_stmt(s) for s in stmt.body]
        elif isinstance(stmt, ForLoop):
            stmt.start = self._fold_expr(stmt.start)
            stmt.limit = self._fold_expr(stmt.limit)
            if stmt.step:
                stmt.step = self._fold_expr(stmt.step)
            stmt.body = [self._fold_stmt(s) for s in stmt.body]
        return stmt

    def _fold_expr(self, expr: Expression) -> Expression:
        if isinstance(expr, (NumberLiteral, CharConstant, Identifier)):
            return expr

        if isinstance(expr, BinaryOp):
            expr.left = self._fold_expr(expr.left)
            expr.right = self._fold_expr(expr.right)
            if _is_constant(expr.left) and _is_constant(expr.right):
                return self._eval_binary(expr)
            return expr

        if isinstance(expr, UnaryOp):
            expr.operand = self._fold_expr(expr.operand)
            if _is_constant(expr.operand):
                return self._eval_unary(expr)
            return expr

        if isinstance(expr, FunctionCall):
            expr.arguments = [self._fold_expr(a) for a in expr.arguments]
            return expr

        return expr

    def _eval_binary(self, expr: BinaryOp) -> NumberLiteral:
        a = _const_value(expr.left)
        b = _const_value(expr.right)
        op = expr.op

        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        elif op == "/":
            result = a // b if b != 0 else 0
        elif op == "mod":
            result = a % b if b != 0 else 0
        elif op == "lsh":
            result = a << b
        elif op == "rsh":
            result = a >> b
        elif op == "and":
            result = a & b
        elif op == "or":
            result = a | b
        elif op == "xor":
            result = a ^ b
        elif op == "=":
            result = 1 if a == b else 0
        elif op == "<>":
            result = 1 if a != b else 0
        elif op == "<":
            result = 1 if a < b else 0
        elif op == ">":
            result = 1 if a > b else 0
        elif op == "<=":
            result = 1 if a <= b else 0
        elif op == ">=":
            result = 1 if a >= b else 0
        else:
            return expr  # unknown op, don't fold

        result = _mask(result, expr.resolved_type)
        return NumberLiteral(
            result, expr.line, expr.column, resolved_type=expr.resolved_type
        )

    def _eval_unary(self, expr: UnaryOp) -> NumberLiteral:
        a = _const_value(expr.operand)

        if expr.op == "-":
            result = -a
        elif expr.op == "%":
            result = ~a
        else:
            return expr

        result = _mask(result, expr.resolved_type)
        return NumberLiteral(
            result, expr.line, expr.column, resolved_type=expr.resolved_type
        )
