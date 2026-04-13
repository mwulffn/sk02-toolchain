"""Code generator for the SK-02 Action! compiler.

Generates SK-02 assembly text from a type-checked, constant-folded AST.
Uses the same instruction set and calling convention as sk02cc.
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
    PointerType,
    ProcCall,
    ProcDecl,
    Program,
    ReturnStmt,
    Statement,
    StringLiteral,
    Type,
    UnaryOp,
    UntilLoop,
    VarDecl,
    WhileLoop,
)
from .call_graph import CallGraph
from .emitter import Emitter
from .type_checker import _INTRINSIC_NAMES


class CodeGenError(Exception):
    """Code generation error."""

    pass


def _is_8bit(t: Type) -> bool:
    return isinstance(t, ByteType)


def _is_16bit(t: Type) -> bool:
    return isinstance(t, (CardType, IntType, PointerType))


class CodeGenerator:
    """Generates SK-02 assembly from Action! AST."""

    def __init__(self, call_graph: CallGraph, origin: int = 0x8000):
        self._em = Emitter()
        self._cg = call_graph
        self._origin = origin
        # Track variable labels for codegen
        self._var_labels: dict[str, dict] = {}  # name → {label, type, size, address}
        self._current_scope: str | None = None
        self._exit_labels: list[str] = []  # stack of loop exit labels
        self.needs_multiply = False
        self.needs_divide = False
        self.needs_divide_16 = False
        self._anon_strings: list[tuple[str, list[int]]] = []
        self._anon_str_counter: int = 0

    def emit(self, line: str) -> None:
        self._em.emit(line)

    def new_label(self, prefix: str = "L") -> str:
        return self._em.new_label(prefix)

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------

    def _var_label(self, name: str) -> str:
        """Get the assembly label for a variable."""
        if self._current_scope:
            scoped = f"{self._current_scope}_{name}"
            if scoped in self._var_labels:
                return self._var_labels[scoped]["label"]
        if name in self._var_labels:
            return self._var_labels[name]["label"]
        raise CodeGenError(f"Unknown variable: {name}")

    def _var_info(self, name: str) -> dict:
        """Get variable info (type, size, etc.)."""
        if self._current_scope:
            scoped = f"{self._current_scope}_{name}"
            if scoped in self._var_labels:
                return self._var_labels[scoped]
        if name in self._var_labels:
            return self._var_labels[name]
        raise CodeGenError(f"Unknown variable: {name}")

    def _register_var(
        self,
        name: str,
        var_type: Type,
        *,
        scope: str | None = None,
        address: int | None = None,
        initial_value: int | None = None,
        initial_values: list[int] | None = None,
    ) -> None:
        """Register a variable for codegen."""
        if isinstance(var_type, ArrayType):
            elem_size = 1 if _is_8bit(var_type.base_type) else 2
            size = elem_size * var_type.size
        else:
            size = 1 if _is_8bit(var_type) else 2
        if scope:
            key = f"{scope}_{name}"
            label = f"_{scope}_{name}"
        else:
            key = name
            label = f"_{name}"
        self._var_labels[key] = {
            "label": label,
            "type": var_type,
            "size": size,
            "address": address,
            "initial_value": initial_value,
            "initial_values": initial_values,
        }

    # ------------------------------------------------------------------
    # Top-level generation
    # ------------------------------------------------------------------

    def generate(self, program: Program) -> str:
        """Generate assembly for the entire program."""
        # Find entry point (last PROC)
        entry_name = None
        for decl in reversed(program.declarations):
            if isinstance(decl, ProcDecl):
                entry_name = decl.name
                break
        if entry_name is None:
            raise CodeGenError("No PROC found — no entry point")

        # Register all variables
        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                self._register_var(
                    decl.name,
                    decl.type,
                    address=decl.address,
                    initial_value=decl.initial_value,
                    initial_values=decl.initial_values,
                )
            elif isinstance(decl, (ProcDecl, FuncDecl)):
                for p in decl.params:
                    self._register_var(p.name, p.type, scope=decl.name)
                for loc in decl.locals:
                    self._register_var(
                        loc.name,
                        loc.type,
                        scope=decl.name,
                        initial_value=loc.initial_value,
                    )

        # Emit header
        self._em.emit_comment("Generated by SK-02 Action! compiler")
        self.emit(f".ORG ${self._origin:04X}")
        self.emit("")

        # Startup: jump to entry point
        self._em.emit_comment("Startup")
        self.emit(f"    GOSUB _{entry_name}")
        self.emit("    HALT")
        self.emit("")

        # Emit all routines
        for decl in program.declarations:
            if isinstance(decl, ProcDecl):
                self._emit_proc(decl)
            elif isinstance(decl, FuncDecl):
                self._emit_func(decl)

        # Runtime routines (only if needed)
        self._emit_runtime_routines()

        # Data section
        self.emit("")
        self._em.emit_comment("Data section")
        self._emit_data_section()

        # SET directives (poke arbitrary addresses in output ROM)
        self._emit_set_directives(program)

        return self._em.get_output()

    # ------------------------------------------------------------------
    # Routines
    # ------------------------------------------------------------------

    def _emit_proc(self, proc: ProcDecl) -> None:
        self._current_scope = proc.name
        self._em.emit_label(f"_{proc.name}")

        # Save params from registers to static storage
        self._emit_param_saves(proc.params, proc.name)

        # Body
        for stmt in proc.body:
            self._emit_stmt(stmt)

        # Final RETURN
        self.emit("    RETURN")
        self.emit("")
        self._current_scope = None

    def _emit_func(self, func: FuncDecl) -> None:
        self._current_scope = func.name
        self._em.emit_label(f"_{func.name}")

        # Save params from registers to static storage
        self._emit_param_saves(func.params, func.name)

        # Body (may contain early RETURNs)
        for stmt in func.body:
            self._emit_stmt(stmt)

        # Final RETURN(expr)
        self._emit_expr(func.return_value)
        self.emit("    RETURN")
        self.emit("")
        self._current_scope = None

    def _emit_param_saves(self, params, scope: str) -> None:
        """Save parameters from registers to static storage locations."""
        for i, param in enumerate(params):
            label = f"_{scope}_{param.name}"
            size = 1 if _is_8bit(param.type) else 2

            if i == 0:
                # Param 1: in A (8-bit) or AB (16-bit)
                if size == 1:
                    self.emit(f"    STORE_A {label}")
                else:
                    self.emit(f"    SET_CD #{label}")
                    self.emit("    ST_AB_CD")
            elif i == 1:
                # Param 2: in B (8-bit) or CD (16-bit)
                if size == 1:
                    self.emit(f"    STORE_B {label}")
                else:
                    # CD holds param 2 (16-bit), need to save it
                    # But CD might be used for the store itself...
                    # Save CD to EF, set CD to label, then move EF to AB and store
                    self.emit("    CD>EF")
                    self.emit(f"    SET_CD #{label}")
                    self.emit("    EF>AB")
                    self.emit("    ST_AB_CD")
            else:
                # Params 3+: on data stack, pop them
                if size == 1:
                    self.emit("    POP_A")
                    self.emit(f"    STORE_A {label}")
                else:
                    self.emit("    POP_A")
                    self.emit("    POP_B")
                    self.emit(f"    SET_CD #{label}")
                    self.emit("    ST_AB_CD")

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _emit_stmt(self, stmt: Statement) -> None:
        if isinstance(stmt, AssignmentStmt):
            self._emit_assignment(stmt)
        elif isinstance(stmt, ProcCall):
            self._emit_proc_call(stmt)
        elif isinstance(stmt, ReturnStmt):
            self._emit_return(stmt)
        elif isinstance(stmt, IfStmt):
            self._emit_if(stmt)
        elif isinstance(stmt, WhileLoop):
            self._emit_while(stmt)
        elif isinstance(stmt, DoLoop):
            self._emit_do_loop(stmt)
        elif isinstance(stmt, UntilLoop):
            self._emit_until(stmt)
        elif isinstance(stmt, ForLoop):
            self._emit_for(stmt)
        elif isinstance(stmt, ExitStmt):
            if not self._exit_labels:
                raise CodeGenError("EXIT outside of loop")
            self.emit(f"    JMP {self._exit_labels[-1]}")

    def _emit_assignment(self, stmt: AssignmentStmt) -> None:
        """Emit assignment: evaluate RHS, store to LHS."""
        if isinstance(stmt.target, Dereference):
            self._emit_deref_store(stmt)
            return

        if isinstance(stmt.target, ArrayAccess):
            self._emit_array_store(stmt)
            return

        if not isinstance(stmt.target, Identifier):
            raise CodeGenError("Only simple variable assignment supported")

        info = self._var_info(stmt.target.name)
        label = info["label"]

        # Evaluate RHS into A (8-bit) or AB (16-bit)
        self._emit_expr(stmt.value)

        # Store
        if info["size"] == 1:
            self.emit(f"    STORE_A {label}")
        else:
            # Zero-extend if RHS is 8-bit but target is 16-bit
            rhs_type = self._expr_resolved_type(stmt.value)
            if rhs_type and not _is_16bit(rhs_type):
                self.emit("    0>B")
            self.emit(f"    SET_CD #{label}")
            self.emit("    ST_AB_CD")

    def _emit_deref_store(self, stmt: AssignmentStmt) -> None:
        """Emit ptr^ = value: load pointer into GH, eval RHS, store via GH."""
        deref = stmt.target
        assert isinstance(deref, Dereference)

        # Load pointer value into AB, then park in GH (free register pair)
        self._emit_expr(deref.operand)
        self.emit("    AB>GH")

        # Evaluate RHS into A (or AB for 16-bit pointee)
        self._emit_expr(stmt.value)

        # Store through GH pointer
        ptr_type = self._expr_resolved_type(deref.operand)
        pointee_16 = isinstance(ptr_type, PointerType) and _is_16bit(ptr_type.base_type)
        if pointee_16:
            self.emit("    STORE_A_GH")
            self.emit("    GH++")
            self.emit("    STORE_B_GH")
        else:
            self.emit("    STORE_A_GH")

    def _emit_proc_call(self, stmt: ProcCall) -> None:
        """Emit procedure call with arguments."""
        self._emit_call_args(stmt.arguments)
        if stmt.name in _INTRINSIC_NAMES:
            self._emit_intrinsic(stmt.name)
        else:
            self.emit(f"    GOSUB _{stmt.name}")

    def _emit_call_args(self, args: list[Expression]) -> None:
        """Emit argument passing for a call."""
        # Push stack params (3+) right-to-left
        if len(args) > 2:
            for i in range(len(args) - 1, 1, -1):
                self._emit_expr(args[i])
                self.emit("    PUSH_A")

        if len(args) >= 2:
            # Evaluate arg 2 into B (or CD for 16-bit)
            self._emit_expr(args[1])
            rt = self._expr_resolved_type(args[1])
            if rt and _is_16bit(rt):
                self.emit("    AB>CD")
            else:
                self.emit("    A>B")

        if len(args) >= 1:
            # Evaluate arg 1 into A (or AB for 16-bit)
            # But if we put arg2 in B, we need to save it first
            if len(args) >= 2:
                self.emit("    PUSH_B")
                self._emit_expr(args[0])
                self.emit("    POP_B")
            else:
                self._emit_expr(args[0])

    def _emit_return(self, stmt: ReturnStmt) -> None:
        """Emit early RETURN (with optional value for FUNC)."""
        if stmt.value is not None:
            self._emit_expr(stmt.value)
        self.emit("    RETURN")

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def _emit_if(self, stmt: IfStmt) -> None:
        end_label = self.new_label("if_end")

        # Main IF condition
        self._emit_condition(stmt.condition)
        if stmt.elseif_clauses or stmt.else_body:
            else_label = self.new_label("else")
            self.emit(f"    JMP_ZERO {else_label}")
        else:
            self.emit(f"    JMP_ZERO {end_label}")

        # THEN body
        for s in stmt.then_body:
            self._emit_stmt(s)

        if stmt.elseif_clauses or stmt.else_body:
            self.emit(f"    JMP {end_label}")
            self._em.emit_label(else_label)

        # ELSEIF clauses
        for i, (cond, body) in enumerate(stmt.elseif_clauses):
            self._emit_condition(cond)
            if i < len(stmt.elseif_clauses) - 1 or stmt.else_body:
                next_label = self.new_label("elif")
                self.emit(f"    JMP_ZERO {next_label}")
            else:
                self.emit(f"    JMP_ZERO {end_label}")

            for s in body:
                self._emit_stmt(s)
            self.emit(f"    JMP {end_label}")

            if i < len(stmt.elseif_clauses) - 1 or stmt.else_body:
                self._em.emit_label(next_label)

        # ELSE body
        if stmt.else_body:
            for s in stmt.else_body:
                self._emit_stmt(s)

        self._em.emit_label(end_label)

    def _emit_while(self, stmt: WhileLoop) -> None:
        loop_label = self.new_label("while")
        end_label = self.new_label("wend")
        self._exit_labels.append(end_label)

        self._em.emit_label(loop_label)
        self._emit_condition(stmt.condition)
        self.emit(f"    JMP_ZERO {end_label}")

        for s in stmt.body:
            self._emit_stmt(s)

        self.emit(f"    JMP {loop_label}")
        self._em.emit_label(end_label)
        self._exit_labels.pop()

    def _emit_do_loop(self, stmt: DoLoop) -> None:
        loop_label = self.new_label("do")
        end_label = self.new_label("do_end")
        self._exit_labels.append(end_label)

        self._em.emit_label(loop_label)
        for s in stmt.body:
            self._emit_stmt(s)
        self.emit(f"    JMP {loop_label}")
        self._em.emit_label(end_label)
        self._exit_labels.pop()

    def _emit_until(self, stmt: UntilLoop) -> None:
        loop_label = self.new_label("until")
        end_label = self.new_label("until_end")
        self._exit_labels.append(end_label)

        self._em.emit_label(loop_label)
        self._emit_condition(stmt.condition)
        # UNTIL exits when condition is TRUE (non-zero)
        # So we jump to end when NON-zero — but JMP_ZERO jumps when zero.
        # Invert: if zero, continue loop; if non-zero, exit
        cont_label = self.new_label("until_cont")
        self.emit(f"    JMP_ZERO {cont_label}")
        self.emit(f"    JMP {end_label}")
        self._em.emit_label(cont_label)

        for s in stmt.body:
            self._emit_stmt(s)
        self.emit(f"    JMP {loop_label}")
        self._em.emit_label(end_label)
        self._exit_labels.pop()

    def _emit_for(self, stmt: ForLoop) -> None:
        loop_label = self.new_label("for")
        end_label = self.new_label("for_end")
        cont_label = self.new_label("for_cont")
        self._exit_labels.append(end_label)

        info = self._var_info(stmt.var_name)
        label = info["label"]

        # Detect step direction for condition reversal
        step_val_raw = 1
        if stmt.step and isinstance(stmt.step, NumberLiteral):
            step_val_raw = stmt.step.value
        counting_down = step_val_raw < 0

        # Initialize loop variable
        self._emit_expr(stmt.start)
        if info["size"] == 1:
            self.emit(f"    STORE_A {label}")
        else:
            # Zero-extend 8-bit start value into B before 16-bit store
            start_type = self._expr_resolved_type(stmt.start)
            if start_type and _is_8bit(start_type):
                self.emit("    0>B")
            self.emit(f"    SET_CD #{label}")
            self.emit("    ST_AB_CD")

        # Loop condition
        self._em.emit_label(loop_label)
        if info["size"] == 1:
            self.emit(f"    LOAD_A {label}")
            self.emit("    PUSH_A")
            self._emit_expr(stmt.limit)
            self.emit("    A>B")
            self.emit("    POP_A")
            self.emit("    CMP")
            if counting_down:
                # Exit when var < limit (overflow = var < limit)
                self.emit(f"    JMP_OVER {end_label}")
                self.emit(f"    JMP {cont_label}")
            else:
                # Exit when var > limit; continue when var <= limit
                self.emit(f"    JMP_OVER {cont_label}")
                self.emit(f"    JMP_ZERO {cont_label}")
                self.emit(f"    JMP {end_label}")
        else:
            # 16-bit: load var into AB, limit into CD, CMP_16
            self.emit(f"    SET_CD #{label}")
            self.emit("    LO_AB_CD")
            self.emit("    PUSH_A")
            self.emit("    PUSH_B")
            self._emit_expr(stmt.limit)
            # Zero-extend 8-bit limit into B if needed
            limit_type = self._expr_resolved_type(stmt.limit)
            if limit_type and _is_8bit(limit_type):
                self.emit("    0>B")
            self.emit("    AB>CD")
            self.emit("    POP_B")
            self.emit("    POP_A")
            self.emit("    CMP_16")
            if counting_down:
                # Exit when var < limit (overflow = var < limit)
                self.emit(f"    JMP_OVER {end_label}")
                self.emit(f"    JMP {cont_label}")
            else:
                # Exit when var > limit; continue when var <= limit
                self.emit(f"    JMP_OVER {cont_label}")
                self.emit(f"    JMP_ZERO {cont_label}")
                self.emit(f"    JMP {end_label}")

        self._em.emit_label(cont_label)
        for s in stmt.body:
            self._emit_stmt(s)

        # Increment (step_val masked to unsigned for assembly)
        step_val = step_val_raw & 0xFFFF if info["size"] == 2 else step_val_raw & 0xFF
        if info["size"] == 1:
            self.emit(f"    LOAD_A {label}")
            self.emit(f"    SET_B #{step_val}")
            self.emit("    ADD")
            self.emit(f"    STORE_A {label}")
        else:
            # 16-bit increment
            self.emit(f"    SET_CD #{label}")
            self.emit("    LO_AB_CD")
            self.emit(f"    SET_CD #{step_val}")
            self.emit("    AB+CD")
            self.emit(f"    SET_CD #{label}")
            self.emit("    ST_AB_CD")
        self.emit(f"    JMP {loop_label}")

        self._em.emit_label(end_label)
        self._exit_labels.pop()

    def _emit_condition(self, condition: Expression) -> None:
        """Emit code for a condition, result in A, then A_ZERO.

        If the condition is a comparison, the comparison codegen already
        leaves 0/1 in A. Otherwise, evaluate and test for zero.
        """
        self._emit_expr(condition)
        # If the expression is a comparison, it already set A to 0/1.
        # A_ZERO sets the zero flag from A. JMP_ZERO will then branch.
        if not isinstance(condition, BinaryOp) or condition.op not in (
            "=",
            "<>",
            "<",
            ">",
            "<=",
            ">=",
        ):
            self.emit("    A_ZERO")
        else:
            self.emit("    A_ZERO")

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _expr_resolved_type(self, expr: Expression) -> Type | None:
        if hasattr(expr, "resolved_type"):
            return expr.resolved_type
        return None

    def _emit_expr(self, expr: Expression) -> None:
        """Emit expression code. Result in A (8-bit) or AB (16-bit)."""
        if isinstance(expr, NumberLiteral):
            rt = self._expr_resolved_type(expr)
            if rt and _is_16bit(rt):
                # Mask to unsigned 16-bit (handles negative INT values)
                val = expr.value & 0xFFFF
                self.emit(f"    SET_AB #{val}")
            else:
                self.emit(f"    SET_A #{expr.value}")

        elif isinstance(expr, CharConstant):
            self.emit(f"    SET_A #{expr.value}")

        elif isinstance(expr, Identifier):
            info = self._var_info(expr.name)
            if info["size"] == 1:
                self.emit(f"    LOAD_A {info['label']}")
            else:
                self.emit(f"    SET_CD #{info['label']}")
                self.emit("    LO_AB_CD")

        elif isinstance(expr, BinaryOp):
            self._emit_binary_op(expr)

        elif isinstance(expr, UnaryOp):
            self._emit_unary_op(expr)

        elif isinstance(expr, FunctionCall):
            self._emit_func_call(expr)

        elif isinstance(expr, Dereference):
            self._emit_deref_load(expr)

        elif isinstance(expr, ArrayAccess):
            self._emit_array_load(expr)

        elif isinstance(expr, StringLiteral):
            s = expr.value
            bytes_data = [len(s)] + [ord(c) for c in s]
            label = f"_str_{self._anon_str_counter}"
            self._anon_str_counter += 1
            self._anon_strings.append((label, bytes_data))
            self.emit(f"    SET_AB #{label}")

    def _emit_deref_load(self, expr: Dereference) -> None:
        """Load value through a pointer: ptr^ → A (or AB for 16-bit pointee)."""
        # Evaluate the pointer expression into AB
        self._emit_expr(expr.operand)
        # Move pointer value to CD for indirect access
        self.emit("    AB>CD")
        rt = self._expr_resolved_type(expr)
        if rt and _is_16bit(rt):
            self.emit("    LO_AB_CD")
        else:
            self.emit("    LOAD_A_CD")

    def _emit_array_load(self, expr: ArrayAccess) -> None:
        """Load array element: arr(index) → A (or AB for 16-bit element)."""
        info = self._var_info(expr.array_name)
        label = info["label"]
        arr_type = info["type"]
        elem_16 = isinstance(arr_type, ArrayType) and _is_16bit(arr_type.base_type)

        # Base address into AB
        self.emit(f"    SET_AB #{label}")
        # Index into CD
        self._emit_expr(expr.index)
        if elem_16:
            # Scale index by 2: shift left 1
            self.emit("    0>B")
            self.emit("    AB>CD")
            self.emit("    CD<<")
        else:
            self.emit("    0>B")
            self.emit("    AB>CD")
        # Restore base address
        self.emit(f"    SET_AB #{label}")
        # Compute element address: base + scaled index
        self.emit("    AB+CD")
        self.emit("    AB>CD")
        # Load element
        if elem_16:
            self.emit("    LO_AB_CD")
        else:
            self.emit("    LOAD_A_CD")

    def _emit_binary_op(self, expr: BinaryOp) -> None:
        """Emit binary operation. Result in A or AB."""
        rt = self._expr_resolved_type(expr)
        is_16 = rt and _is_16bit(rt)

        # Comparisons
        if expr.op in ("=", "<>", "<", ">", "<=", ">="):
            self._emit_comparison(expr)
            return

        left_type = self._expr_resolved_type(expr.left)
        right_type = self._expr_resolved_type(expr.right)

        # Evaluate left
        self._emit_expr(expr.left)

        if is_16:
            if not _is_16bit(left_type):
                self.emit("    0>B")  # zero-extend 8-bit left operand to 16-bit
            self.emit("    PUSH_A")
            self.emit("    PUSH_B")
        else:
            self.emit("    PUSH_A")

        # Evaluate right
        self._emit_expr(expr.right)

        if is_16:
            if not _is_16bit(right_type):
                self.emit("    0>B")  # zero-extend 8-bit right operand to 16-bit
            self.emit("    AB>CD")
            self.emit("    POP_B")
            self.emit("    POP_A")
        else:
            self.emit("    A>B")
            self.emit("    POP_A")

        # Operation
        if expr.op == "+":
            self.emit("    AB+CD" if is_16 else "    ADD")
        elif expr.op == "-":
            self.emit("    AB-CD" if is_16 else "    SUB")
        elif expr.op == "and":
            self.emit("    AND")
        elif expr.op == "or":
            self.emit("    OR")
        elif expr.op == "xor":
            self.emit("    XOR")
        elif expr.op == "*":
            if is_16:
                pass  # AB = left, CD = right — __rt_mul handles full 16-bit
            else:
                # A = left, B = right → need AB=(left,0), CD=(right,0)
                self.emit("    PUSH_A")
                self.emit("    0>A")
                self.emit("    A>D")
                self.emit("    B>C")
                self.emit("    0>B")
                self.emit("    POP_A")
            self.emit("    GOSUB __rt_mul")
            self.needs_multiply = True
        elif expr.op in ("/", "mod"):
            if is_16:
                # AB = dividend, CD = divisor — use 16-bit divide routine
                self.emit("    GOSUB __rt_div_16")
                if expr.op == "mod":
                    self.emit("    CD>AB")  # remainder in CD → move to AB
                self.needs_divide_16 = True
            else:
                # A = dividend, B = divisor → need A=dividend, C=divisor
                self.emit("    PUSH_A")
                self.emit("    0>A")
                self.emit("    A>D")
                self.emit("    B>C")
                self.emit("    0>B")
                self.emit("    POP_A")
                self.emit("    GOSUB __rt_div")
                if expr.op == "mod":
                    self.emit("    C>A")
                self.needs_divide = True
        elif expr.op == "lsh":
            self._emit_shift_left(is_16)
        elif expr.op == "rsh":
            self._emit_shift_right(is_16)

    def _emit_shift_left(self, is_16: bool) -> None:
        """Emit left shift: A (or AB) << B times."""
        loop_label = self.new_label("shl")
        end_label = self.new_label("shl_end")
        self.emit("    PUSH_A")
        self._em.emit_label(loop_label)
        self.emit("    B>A")
        self.emit("    A_ZERO")
        self.emit(f"    JMP_ZERO {end_label}")
        self.emit("    A>B")
        self.emit("    POP_A")
        self.emit("    AB<<" if is_16 else "    A<<")
        self.emit("    PUSH_A")
        self.emit("    B--")
        self.emit(f"    JMP {loop_label}")
        self._em.emit_label(end_label)
        self.emit("    POP_A")

    def _emit_shift_right(self, is_16: bool) -> None:
        """Emit right shift: A (or AB) >> B times."""
        loop_label = self.new_label("shr")
        end_label = self.new_label("shr_end")
        self.emit("    PUSH_A")
        self._em.emit_label(loop_label)
        self.emit("    B>A")
        self.emit("    A_ZERO")
        self.emit(f"    JMP_ZERO {end_label}")
        self.emit("    A>B")
        self.emit("    POP_A")
        self.emit("    AB>>" if is_16 else "    A>>")
        self.emit("    PUSH_A")
        self.emit("    B--")
        self.emit(f"    JMP {loop_label}")
        self._em.emit_label(end_label)
        self.emit("    POP_A")

    def _emit_comparison(self, expr: BinaryOp) -> None:
        """Emit comparison, leaving 0 or 1 in A."""
        # Determine if 16-bit comparison
        left_rt = self._expr_resolved_type(expr.left)
        right_rt = self._expr_resolved_type(expr.right)
        is_16 = (left_rt and _is_16bit(left_rt)) or (right_rt and _is_16bit(right_rt))

        # Evaluate left
        self._emit_expr(expr.left)
        if is_16:
            self.emit("    PUSH_A")
            self.emit("    PUSH_B")
        else:
            self.emit("    PUSH_A")

        # Evaluate right
        self._emit_expr(expr.right)

        if is_16:
            self.emit("    AB>CD")
            self.emit("    POP_B")
            self.emit("    POP_A")
            self.emit("    CMP_16")
        else:
            self.emit("    A>B")
            self.emit("    POP_A")
            self.emit("    CMP")

        # Branch to set result
        false_label = self.new_label("false")
        true_label = self.new_label("true")
        end_label = self.new_label("cmp_end")

        op = expr.op
        if op == "=":
            self.emit(f"    JMP_ZERO {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == "<>":
            self.emit(f"    JMP_ZERO {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == "<":
            self.emit(f"    JMP_OVER {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == ">=":
            self.emit(f"    JMP_OVER {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == ">":
            self.emit(f"    JMP_OVER {false_label}")
            self.emit(f"    JMP_ZERO {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == "<=":
            self.emit(f"    JMP_OVER {true_label}")
            self.emit(f"    JMP_ZERO {true_label}")
            self.emit(f"    JMP {false_label}")

        self._em.emit_label(true_label)
        self.emit("    SET_A #1")
        self.emit(f"    JMP {end_label}")
        self._em.emit_label(false_label)
        self.emit("    SET_A #0")
        self._em.emit_label(end_label)

    def _emit_unary_op(self, expr: UnaryOp) -> None:
        """Emit unary operation."""
        if expr.op == "@":
            # Address-of: load the label address into AB
            if isinstance(expr.operand, Identifier):
                label = self._var_label(expr.operand.name)
                self.emit(f"    SET_AB #{label}")
            else:
                raise CodeGenError("Address-of requires a variable")
            return
        self._emit_expr(expr.operand)
        if expr.op == "-":
            # Negate: 0 - A
            self.emit("    A>B")
            self.emit("    0>A")
            self.emit("    SUB")
        elif expr.op == "%":
            # Bitwise NOT
            self.emit("    NOT")

    def _emit_func_call(self, expr: FunctionCall) -> None:
        """Emit function call in expression context."""
        self._emit_call_args(expr.arguments)
        if expr.name in _INTRINSIC_NAMES:
            self._emit_intrinsic(expr.name)
        else:
            self.emit(f"    GOSUB _{expr.name}")

    def _emit_intrinsic(self, name: str) -> None:
        """Emit inline instructions for an I/O intrinsic."""
        if name == "gpioread":
            self.emit("    GPIO>A")
        elif name == "gpiowrite":
            self.emit("    A>GPIO")
        elif name == "readx":
            self.emit("    X>A")
        elif name == "ready":
            self.emit("    Y>A")
        elif name == "out0write":
            self.emit("    A>OUT_0")
        elif name == "out1write":
            self.emit("    A>OUT_1")
        elif name == "outwrite":
            self.emit("    AB>OUT")
        elif name == "hwivalue":
            self.emit("    HWI>A")
        elif name == "triggerhwi":
            self.emit("    TRG_HWI")
        elif name == "clearinterrupt":
            self.emit("    CLEAR_INTER")
        elif name == "interruptflag":
            skip = self.new_label("Linter")
            self.emit("    SET_A #1")
            self.emit(f"    JMP_INTER {skip}")
            self.emit("    SET_A #0")
            self.emit(f"{skip}:")
        else:
            raise CodeGenError(f"Unknown intrinsic: {name}")

    def _emit_array_store(self, stmt: AssignmentStmt) -> None:
        """Emit arr(index) = value: compute address into GH, eval RHS, store."""
        access = stmt.target
        assert isinstance(access, ArrayAccess)

        info = self._var_info(access.array_name)
        label = info["label"]
        arr_type = info["type"]
        elem_16 = isinstance(arr_type, ArrayType) and _is_16bit(arr_type.base_type)

        # Compute element address into AB
        self.emit(f"    SET_AB #{label}")
        self._emit_expr(access.index)
        if elem_16:
            self.emit("    0>B")
            self.emit("    AB>CD")
            self.emit("    CD<<")
        else:
            self.emit("    0>B")
            self.emit("    AB>CD")
        self.emit(f"    SET_AB #{label}")
        self.emit("    AB+CD")
        # Park address in GH
        self.emit("    AB>GH")

        # Evaluate RHS
        self._emit_expr(stmt.value)

        # Store through GH
        if elem_16:
            self.emit("    STORE_A_GH")
            self.emit("    GH++")
            self.emit("    STORE_B_GH")
        else:
            self.emit("    STORE_A_GH")

    # ------------------------------------------------------------------
    # Runtime routines
    # ------------------------------------------------------------------

    def _emit_runtime_routines(self) -> None:
        """Emit software multiply/divide subroutines, only if used."""
        if self.needs_multiply:
            self.emit("")
            self._em.emit_comment(
                "Software multiply: AB = AB * CD (8-bit operands, 16-bit result)"
            )
            self.emit("__rt_mul:")
            self.emit("    PUSH_E")
            self.emit("    PUSH_F")
            self.emit("    PUSH_G")
            self.emit("    PUSH_H")
            self.emit("    PUSH_A")
            self.emit("    SET_A #16")
            self.emit("    A>G")
            self.emit("    POP_A")
            self.emit("    AB>EF")
            self.emit("    0>A")
            self.emit("    0>B")
            self.emit("__rt_mul_loop:")
            self.emit("    PUSH_A")
            self.emit("    E>A")
            self.emit("    JMP_A_EVEN __rt_mul_skip")
            self.emit("    POP_A")
            self.emit("    AB+CD")
            self.emit("    JMP __rt_mul_next")
            self.emit("__rt_mul_skip:")
            self.emit("    POP_A")
            self.emit("__rt_mul_next:")
            self.emit("    PUSH_A")
            self.emit("    EF>>")
            self.emit("    CD<<")
            self.emit("    G>A")
            self.emit("    A--")
            self.emit("    A>G")
            self.emit("    POP_A")
            self.emit("    JMP_ZERO __rt_mul_done")
            self.emit("    JMP __rt_mul_loop")
            self.emit("__rt_mul_done:")
            self.emit("    POP_H")
            self.emit("    POP_G")
            self.emit("    POP_F")
            self.emit("    POP_E")
            self.emit("    RETURN")

        if self.needs_divide:
            self.emit("")
            self._em.emit_comment("Software divide: A=dividend, C=divisor.")
            self._em.emit_comment(
                "Returns: A=quotient, C=remainder. Halts on divide by zero."
            )
            self.emit("__rt_div:")
            self.emit("    PUSH_E")
            self.emit("    PUSH_H")
            self.emit("    A>H")
            self.emit("    C>A")
            self.emit("    A_ZERO")
            self.emit("    JMP_ZERO __rt_div_halt")
            self.emit("    H>A")
            self.emit("    A>H")
            self.emit("    0>A")
            self.emit("    A>E")
            self.emit("    H>A")
            self.emit("__rt_div_loop:")
            self.emit("    CMP_C")
            self.emit("    JMP_OVER __rt_div_done")
            self.emit("    SUB_C")
            self.emit("    A>H")
            self.emit("    E>A")
            self.emit("    A++")
            self.emit("    A>E")
            self.emit("    H>A")
            self.emit("    JMP __rt_div_loop")
            self.emit("__rt_div_halt:")
            self.emit("    HALT")
            self.emit("__rt_div_done:")
            self.emit("    A>H")
            self.emit("    E>A")
            self.emit("    H>C")
            self.emit("    POP_H")
            self.emit("    POP_E")
            self.emit("    RETURN")

        if self.needs_divide_16:
            self.emit("")
            self._em.emit_comment("16-bit divide: AB=dividend, CD=divisor.")
            self._em.emit_comment(
                "Returns: AB=quotient, CD=remainder. Halts on divide by zero."
            )
            self.emit("__rt_div_16:")
            self.emit("    PUSH_E")
            self.emit("    PUSH_F")
            self.emit("    PUSH_G")
            self.emit("    PUSH_H")
            # Save dividend so divisor check (which uses A/B) doesn't clobber it
            self.emit("    AB>GH")  # GH = dividend (temp)
            self.emit("    C>A")
            self.emit("    D>B")
            self.emit("    OR")  # A = C | D; zero flag if divisor == 0
            self.emit("    JMP_ZERO __rt_div_16_halt")
            self.emit("    CD>EF")  # EF = divisor (save)
            self.emit("    GH>AB")  # AB = dividend (restore)
            # GH = 0 (quotient): zero G and H via A without losing A
            self.emit("    PUSH_A")
            self.emit("    0>A")
            self.emit("    A>G")
            self.emit("    A>H")
            self.emit("    POP_A")  # AB = dividend, GH = 0
            # AB = remainder (starts as full dividend), EF = divisor, GH = quotient
            self.emit("__rt_div_16_loop:")
            self.emit("    EF>CD")  # CD = divisor
            self.emit("    CMP_16")  # overflow if AB < CD
            self.emit("    JMP_OVER __rt_div_16_done")
            self.emit("    AB-CD")  # remainder -= divisor
            self.emit("    GH++")  # quotient++
            self.emit("    JMP __rt_div_16_loop")
            self.emit("__rt_div_16_halt:")
            self.emit("    HALT")
            self.emit("__rt_div_16_done:")
            self.emit("    AB>CD")  # CD = remainder
            self.emit("    GH>AB")  # AB = quotient
            self.emit("    POP_H")
            self.emit("    POP_G")
            self.emit("    POP_F")
            self.emit("    POP_E")
            self.emit("    RETURN")

    # ------------------------------------------------------------------
    # Data section
    # ------------------------------------------------------------------

    def _emit_data_section(self) -> None:
        """Emit storage for all variables and anonymous string literals."""
        for key, info in self._var_labels.items():
            label = info["label"]
            address = info.get("address")
            init = info.get("initial_value")
            size = info["size"]

            var_type = info.get("type")
            is_array = isinstance(var_type, ArrayType)

            if address is not None:
                # Address-placed variable: emit .EQU
                self.emit(f".EQU {label}, ${address:04X}")
            elif is_array:
                arr_type = var_type
                self._em.emit_label(label)
                elem_size = 1 if _is_8bit(arr_type.base_type) else 2
                init_vals = info.get("initial_values")
                if init_vals is not None:
                    data = ", ".join(str(v) for v in init_vals)
                    if elem_size == 1:
                        self.emit(f"    .BYTE {data}")
                    else:
                        self.emit(f"    .WORD {data}")
                else:
                    count = arr_type.size
                    zeros = ", ".join(["0"] * count)
                    if elem_size == 1:
                        self.emit(f"    .BYTE {zeros}")
                    else:
                        self.emit(f"    .WORD {zeros}")
            else:
                self._em.emit_label(label)
                if init is not None:
                    if size == 1:
                        self.emit(f"    .BYTE {init}")
                    else:
                        self.emit(f"    .WORD {init}")
                else:
                    if size == 1:
                        self.emit("    .BYTE 0")
                    else:
                        self.emit("    .WORD 0")

        # Anonymous string literals allocated during expression codegen
        for label, bytes_data in self._anon_strings:
            self._em.emit_label(label)
            data = ", ".join(str(v) for v in bytes_data)
            self.emit(f"    .BYTE {data}")

    def _emit_set_directives(self, program: Program) -> None:
        """Emit SET directives as .ORG + .WORD patches at end of output."""
        for directive in program.directives:
            val = directive.value
            label = f"_{val}" if isinstance(val, str) else str(val)
            self.emit("")
            self.emit(f".ORG ${directive.target_addr:04X}")
            self.emit(f"    .WORD {label}")
