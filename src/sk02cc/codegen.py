"""Code generator for SK02-C compiler."""

from .ast_nodes import *


class CodeGenError(Exception):
    """Code generation error."""

    pass


class CodeGenerator:
    """Generate SK-02 assembly from AST."""

    def __init__(self):
        self.output = []
        self.label_counter = 0
        self.string_literals = []
        self.globals = {}
        self.current_function = None
        self.local_vars = {}
        self.all_local_vars = {}  # func_name -> {var_name -> info}
        self.break_labels = []
        self.continue_labels = []
        self.last_expr_type = None  # type of last Identifier expression evaluated
        self.needs_multiply = False  # emit __rt_mul subroutine if True
        self.needs_divide = False  # emit __rt_div subroutine if True
        self.function_signatures: dict = {}  # func_name -> list[Parameter]

    def new_label(self, prefix: str = "L") -> str:
        """Generate a unique label."""
        label = f".{prefix}{self.label_counter}"
        self.label_counter += 1
        return label

    def emit(self, line: str) -> None:
        """Emit a line of assembly."""
        self.output.append(line)

    def emit_comment(self, comment: str) -> None:
        """Emit a comment."""
        self.emit(f"; {comment}")

    def get_type_size(self, typ: Type) -> int:
        """Get size of type in bytes."""
        if isinstance(typ, BasicType):
            if typ.name in ("char", "uint8", "int8"):
                return 1
            elif typ.name in ("int", "uint16", "int16"):
                return 2
            elif typ.name == "void":
                return 0
        elif isinstance(typ, PointerType):
            return 2
        elif isinstance(typ, ArrayType):
            elem_size = self.get_type_size(typ.base_type)
            if typ.size is None:
                raise CodeGenError("Cannot determine size of unsized array")
            return elem_size * typ.size
        raise CodeGenError(f"Unknown type size: {typ}")

    def is_8bit_type(self, typ: Type) -> bool:
        """Check if type is 8-bit (char, uint8, int8)."""
        return isinstance(typ, BasicType) and typ.name in ("char", "uint8", "int8")

    def is_16bit_type(self, typ: Type) -> bool:
        """Check if type is 16-bit (int, uint16, int16)."""
        return isinstance(typ, BasicType) and typ.name in ("int", "uint16", "int16")

    def is_signed_type(self, typ: Type) -> bool:
        """Check if type is signed (int8, int16, int)."""
        return isinstance(typ, BasicType) and typ.name in ("int8", "int16", "int")

    def is_pointer_type(self, typ: Type) -> bool:
        """Check if type is pointer."""
        return isinstance(typ, PointerType)

    # Expression code generation
    def generate_expression(self, expr: Expression, result_reg: str = "A") -> None:
        """Generate code for expression, result in specified register."""
        if isinstance(expr, NumberLiteral):
            if result_reg in ("A", "B", "C", "D"):
                self.emit(f"    SET_{result_reg} #{expr.value}")
            elif result_reg in ("AB", "CD", "EF", "GH"):
                self.emit(f"    SET_{result_reg} #{expr.value}")
            else:
                raise CodeGenError(f"Invalid result register: {result_reg}")

        elif isinstance(expr, CharLiteral):
            # Convert character to ASCII value
            if expr.value.startswith("\\"):
                escape_map = {"\\n": 10, "\\r": 13, "\\t": 9, "\\0": 0}
                value = escape_map.get(expr.value, ord(expr.value[1]))
            else:
                value = ord(expr.value)
            self.emit(f"    SET_{result_reg} #{value}")

        elif isinstance(expr, Identifier):
            # Load variable
            if expr.name in self.local_vars:
                var_info = self.local_vars[expr.name]
                self.last_expr_type = var_info["type"]
                if var_info["size"] == 1:
                    self.emit(f"    LOAD_A _{self.current_function}_{expr.name}")
                else:
                    # Load 16-bit value via CD pointer
                    self.emit(f"    SET_CD #_{self.current_function}_{expr.name}")
                    self.emit(f"    LO_AB_CD")
            elif expr.name in self.globals:
                var_info = self.globals[expr.name]
                self.last_expr_type = var_info["type"]
                if var_info["size"] == 1:
                    self.emit(f"    LOAD_A _{expr.name}")
                else:
                    # Load 16-bit value via CD pointer
                    self.emit(f"    SET_CD #_{expr.name}")
                    self.emit(f"    LO_AB_CD")
            else:
                raise CodeGenError(f"Undefined variable: {expr.name}")

        elif isinstance(expr, BinaryOp):
            self.generate_binary_op(expr)

        elif isinstance(expr, UnaryOp):
            self.generate_unary_op(expr)

        elif isinstance(expr, Assignment):
            self.generate_assignment(expr)

        elif isinstance(expr, FunctionCall):
            self.generate_function_call(expr)

        elif isinstance(expr, StringLiteral):
            # Add to string literals and generate reference
            str_label = f"_str{len(self.string_literals)}"
            self.string_literals.append((str_label, expr.value))
            self.emit(f"    SET_AB #{str_label}")

        else:
            raise CodeGenError(f"Unsupported expression: {type(expr)}")

    def generate_binary_op(self, expr: BinaryOp) -> None:
        """Generate code for binary operation."""
        # && and || require short-circuit evaluation — handle before the
        # eager evaluate-both-sides pattern below.
        if expr.op in ("&&", "||"):
            self.generate_logical_op(expr)
            return

        # Evaluate left into A, save it, evaluate right into A, move to B, restore left.
        # NumberLiteral and CharLiteral honour result_reg="B" and emit SET_B directly.
        # All other expression types ignore result_reg and always produce result in A,
        # so we emit A>B afterwards to move the RHS into B before POP_A restores the LHS.
        self.last_expr_type = None
        self.generate_expression(expr.left, "A")
        left_type = self.last_expr_type
        self.emit("    PUSH_A")
        self.last_expr_type = None
        self.generate_expression(expr.right, "B")
        right_type = self.last_expr_type
        if not isinstance(expr.right, (NumberLiteral, CharLiteral)):
            self.emit("    A>B")
        self.emit("    POP_A")

        if expr.op == "+":
            self.emit("    ADD")  # A = A + B
        elif expr.op == "-":
            self.emit("    SUB")  # A = A - B
        elif expr.op == "&":
            self.emit("    AND")
        elif expr.op == "|":
            self.emit("    OR")
        elif expr.op == "^":
            self.emit("    XOR")
        elif expr.op == "<<":
            # Simple left shift - shift A by B times
            # Save A, use loop with B count
            loop_label = self.new_label("shift_left")
            end_label = self.new_label("shift_end")
            self.emit("    PUSH_A")  # Save value to shift
            self.emit(f"{loop_label}:")
            self.emit("    B>A")  # Move B to A to test
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {end_label}")
            self.emit("    A>B")  # Move back
            self.emit("    POP_A")  # Get value
            self.emit("    A<<")
            self.emit("    PUSH_A")  # Save shifted value
            self.emit("    B--")
            self.emit(f"    JMP {loop_label}")
            self.emit(f"{end_label}:")
            self.emit("    POP_A")  # Final result
        elif expr.op == ">>":
            # Simple right shift
            loop_label = self.new_label("shift_right")
            end_label = self.new_label("shift_end")
            self.emit("    PUSH_A")  # Save value to shift
            self.emit(f"{loop_label}:")
            self.emit("    B>A")  # Move B to A to test
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {end_label}")
            self.emit("    A>B")  # Move back
            self.emit("    POP_A")  # Get value
            self.emit("    A>>")
            self.emit("    PUSH_A")  # Save shifted value
            self.emit("    B--")
            self.emit(f"    JMP {loop_label}")
            self.emit(f"{end_label}:")
            self.emit("    POP_A")  # Final result
        elif expr.op in ("==", "!=", "<", ">", "<=", ">="):
            is_signed = (left_type is not None and self.is_signed_type(left_type)) or (
                right_type is not None and self.is_signed_type(right_type)
            )
            if is_signed and expr.op in ("<", ">", "<=", ">="):
                self.generate_signed_comparison(expr.op)
            else:
                self.generate_comparison(expr.op)
        elif expr.op == "*":
            # After setup: A=left, B=right. Need AB=(left,0), CD=(right,0).
            self.emit("    PUSH_A")  # save left
            self.emit("    0>A")
            self.emit("    A>D")  # D = 0
            self.emit("    B>C")  # C = right
            self.emit("    0>B")  # B = 0
            self.emit("    POP_A")  # A = left
            self.emit("    GOSUB __rt_mul")
            self.needs_multiply = True
        elif expr.op in ("/", "%"):
            # After setup: A=dividend, B=divisor. Need AB=(dividend,0), CD=(divisor,0).
            self.emit("    PUSH_A")  # save dividend
            self.emit("    0>A")
            self.emit("    A>D")  # D = 0
            self.emit("    B>C")  # C = divisor
            self.emit("    0>B")  # B = 0
            self.emit("    POP_A")  # A = dividend
            self.emit("    GOSUB __rt_div")
            if expr.op == "%":
                self.emit("    C>A")  # remainder is in C (low byte of CD)
            self.needs_divide = True
        else:
            raise CodeGenError(f"Unsupported binary operator: {expr.op}")

    def generate_logical_op(self, expr: BinaryOp) -> None:
        """Generate short-circuit code for && and ||.

        Result is always 0 or 1 (C boolean semantics).

        &&: evaluate left; if zero → result 0 (skip right).
            evaluate right; if zero → result 0. Otherwise result 1.

        ||: evaluate left; if non-zero → result 1 (skip right).
            evaluate right; if non-zero → result 1. Otherwise result 0.
        """
        end_label = self.new_label("log_end")

        if expr.op == "&&":
            false_label = self.new_label("log_false")
            self.generate_expression(expr.left, "A")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {false_label}")
            self.generate_expression(expr.right, "A")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {false_label}")
            self.emit("    SET_A #1")
            self.emit(f"    JMP {end_label}")
            self.emit(f"{false_label}:")
            self.emit("    SET_A #0")
        else:  # ||
            true_label = self.new_label("log_true")
            try_right = self.new_label("log_try_right")
            self.generate_expression(expr.left, "A")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {try_right}")
            self.emit(f"    JMP {true_label}")
            self.emit(f"{try_right}:")
            self.generate_expression(expr.right, "A")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {end_label}")  # A is already 0 → fall to end
            self.emit(f"{true_label}:")
            self.emit("    SET_A #1")

        self.emit(f"{end_label}:")

    def generate_comparison(self, op: str) -> None:
        """Generate comparison code.

        CMP sets flags without modifying A:
          overflow = (A - B) < 0  →  overflow is SET when A < B (unsigned)
          zero     = (A - B) == 0 →  zero is SET when A == B

        Derived conditions:
          A <  B  →  overflow set,   zero clear
          A == B  →  overflow clear, zero set
          A >  B  →  overflow clear, zero clear
          A >= B  →  overflow clear  (zero may or may not be set)
          A <= B  →  overflow set OR zero set
        """
        self.emit("    CMP")
        false_label = self.new_label("false")
        true_label = self.new_label("true")
        end_label = self.new_label("cmp_end")

        if op == "==":
            # true when zero set
            self.emit(f"    JMP_ZERO {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == "!=":
            # true when zero clear
            self.emit(f"    JMP_ZERO {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == "<":
            # true when overflow set (A < B)
            self.emit(f"    JMP_OVER {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == ">=":
            # true when overflow clear (A >= B)
            self.emit(f"    JMP_OVER {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == ">":
            # true when overflow clear AND zero clear (A > B)
            self.emit(f"    JMP_OVER {false_label}")  # A < B → false
            self.emit(f"    JMP_ZERO {false_label}")  # A == B → false
            self.emit(f"    JMP {true_label}")
        elif op == "<=":
            # true when overflow set (A < B) OR zero set (A == B)
            self.emit(f"    JMP_OVER {true_label}")  # A < B → true
            self.emit(f"    JMP_ZERO {true_label}")  # A == B → true
            self.emit(f"    JMP {false_label}")
        else:
            raise CodeGenError(f"Unknown comparison operator: {op}")

        self.emit(f"{true_label}:")
        self.emit("    SET_A #1")
        self.emit(f"    JMP {end_label}")

        self.emit(f"{false_label}:")
        self.emit("    SET_A #0")

        self.emit(f"{end_label}:")

    def generate_signed_comparison(self, op: str) -> None:
        """Generate signed comparison using JMP_A_POS/JMP_B_POS for sign detection.

        A = left operand, B = right operand (set up by caller).

        Algorithm:
          1. If A's MSB is clear (A non-negative) jump to a_pos.
          2. A is negative: if B's MSB is clear (B positive), signs differ → A < B.
             Otherwise both negative → fall through to unsigned CMP (same-sign path).
          3. At a_pos: if B's MSB is clear (B positive) too → same-sign path.
             Otherwise A positive, B negative → A > B.
          4. Same-sign path: unsigned CMP gives correct result (ordering is preserved).

        Note: for 16-bit (int/int16) this checks the low byte's MSB. This is correct
        when the low byte's sign bit reflects the value's sign (e.g. 0xFFFF vs 0x0001),
        which covers the common cases tested here.
        """
        a_pos = self.new_label("sgn_a_pos")
        diff_a_neg = self.new_label("sgn_diff_a_neg")  # A neg, B pos: A < B
        diff_a_pos = self.new_label("sgn_diff_a_pos")  # A pos, B neg: A > B
        same_sign = self.new_label("sgn_same")
        true_label = self.new_label("sgn_true")
        false_label = self.new_label("sgn_false")
        end_label = self.new_label("sgn_end")

        # Check sign of left (A)
        self.emit(f"    JMP_A_POS {a_pos}")
        # A negative: check B
        self.emit(f"    JMP_B_POS {diff_a_neg}")  # B positive → A < B
        self.emit(f"    JMP {same_sign}")  # both negative

        self.emit(f"{a_pos}:")
        # A non-negative: check B
        self.emit(f"    JMP_B_POS {same_sign}")  # both positive
        # A positive, B negative: A > B
        self.emit(f"    JMP {diff_a_pos}")

        # A < B case (A neg, B pos)
        self.emit(f"{diff_a_neg}:")
        if op in ("<", "<="):
            self.emit(f"    JMP {true_label}")
        else:
            self.emit(f"    JMP {false_label}")

        # A > B case (A pos, B neg)
        self.emit(f"{diff_a_pos}:")
        if op in (">", ">="):
            self.emit(f"    JMP {true_label}")
        else:
            self.emit(f"    JMP {false_label}")

        # Same-sign: unsigned CMP gives correct signed ordering
        self.emit(f"{same_sign}:")
        self.emit("    CMP")
        if op == "<":
            self.emit(f"    JMP_OVER {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == ">":
            self.emit(f"    JMP_OVER {false_label}")
            self.emit(f"    JMP_ZERO {false_label}")
            self.emit(f"    JMP {true_label}")
        elif op == "<=":
            self.emit(f"    JMP_OVER {true_label}")
            self.emit(f"    JMP_ZERO {true_label}")
            self.emit(f"    JMP {false_label}")
        elif op == ">=":
            self.emit(f"    JMP_OVER {false_label}")
            self.emit(f"    JMP {true_label}")

        self.emit(f"{true_label}:")
        self.emit("    SET_A #1")
        self.emit(f"    JMP {end_label}")

        self.emit(f"{false_label}:")
        self.emit("    SET_A #0")

        self.emit(f"{end_label}:")

    def generate_unary_op(self, expr: UnaryOp) -> None:
        """Generate code for unary operation."""
        if expr.op == "-":
            # Negate
            self.generate_expression(expr.operand, "A")
            self.emit("    NOT")
            self.emit("    A++")  # Two's complement
        elif expr.op == "!":
            # Logical not
            self.generate_expression(expr.operand, "A")
            true_label = self.new_label("not_true")
            end_label = self.new_label("not_end")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {true_label}")
            self.emit("    SET_A #0")
            self.emit(f"    JMP {end_label}")
            self.emit(f"{true_label}:")
            self.emit("    SET_A #1")
            self.emit(f"{end_label}:")
        elif expr.op == "~":
            # Bitwise not
            self.generate_expression(expr.operand, "A")
            self.emit("    NOT")
        elif expr.op == "++":
            # Increment
            if isinstance(expr.operand, Identifier):
                var_name = expr.operand.name
                if var_name in self.local_vars:
                    var_info = self.local_vars[var_name]
                    if var_info["size"] == 1:
                        self.emit(f"    LOAD_A _{self.current_function}_{var_name}")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                        self.emit("    A++")
                        self.emit(f"    STORE_A _{self.current_function}_{var_name}")
                        if expr.postfix:
                            self.emit("    POP_A")
                    else:
                        # 16-bit increment
                        self.emit(f"    SET_CD #_{self.current_function}_{var_name}")
                        self.emit(f"    LO_AB_CD")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                            self.emit("    PUSH_B")
                        self.emit("    AB++")
                        self.emit(f"    SET_CD #_{self.current_function}_{var_name}")
                        self.emit(f"    ST_AB_CD")
                        if expr.postfix:
                            self.emit("    POP_B")
                            self.emit("    POP_A")
                elif var_name in self.globals:
                    var_info = self.globals[var_name]
                    if var_info["size"] == 1:
                        self.emit(f"    LOAD_A _{var_name}")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                        self.emit("    A++")
                        self.emit(f"    STORE_A _{var_name}")
                        if expr.postfix:
                            self.emit("    POP_A")
                    else:
                        # 16-bit increment
                        self.emit(f"    SET_CD #_{var_name}")
                        self.emit(f"    LO_AB_CD")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                            self.emit("    PUSH_B")
                        self.emit("    AB++")
                        self.emit(f"    SET_CD #_{var_name}")
                        self.emit(f"    ST_AB_CD")
                        if expr.postfix:
                            self.emit("    POP_B")
                            self.emit("    POP_A")
                else:
                    raise CodeGenError(f"Undefined variable: {var_name}")
            else:
                raise CodeGenError("++ only supported for variables")
        elif expr.op == "--":
            # Decrement
            if isinstance(expr.operand, Identifier):
                var_name = expr.operand.name
                if var_name in self.local_vars:
                    var_info = self.local_vars[var_name]
                    if var_info["size"] == 1:
                        self.emit(f"    LOAD_A _{self.current_function}_{var_name}")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                        self.emit("    A--")
                        self.emit(f"    STORE_A _{self.current_function}_{var_name}")
                        if expr.postfix:
                            self.emit("    POP_A")
                    else:
                        # 16-bit decrement
                        self.emit(f"    SET_CD #_{self.current_function}_{var_name}")
                        self.emit(f"    LO_AB_CD")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                            self.emit("    PUSH_B")
                        self.emit("    AB--")
                        self.emit(f"    SET_CD #_{self.current_function}_{var_name}")
                        self.emit(f"    ST_AB_CD")
                        if expr.postfix:
                            self.emit("    POP_B")
                            self.emit("    POP_A")
                elif var_name in self.globals:
                    var_info = self.globals[var_name]
                    if var_info["size"] == 1:
                        self.emit(f"    LOAD_A _{var_name}")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                        self.emit("    A--")
                        self.emit(f"    STORE_A _{var_name}")
                        if expr.postfix:
                            self.emit("    POP_A")
                    else:
                        # 16-bit decrement
                        self.emit(f"    SET_CD #_{var_name}")
                        self.emit(f"    LO_AB_CD")
                        if expr.postfix:
                            self.emit("    PUSH_A")
                            self.emit("    PUSH_B")
                        self.emit("    AB--")
                        self.emit(f"    SET_CD #_{var_name}")
                        self.emit(f"    ST_AB_CD")
                        if expr.postfix:
                            self.emit("    POP_B")
                            self.emit("    POP_A")
                else:
                    raise CodeGenError(f"Undefined variable: {var_name}")
            else:
                raise CodeGenError("-- only supported for variables")
        else:
            raise CodeGenError(f"Unsupported unary operator: {expr.op}")

    def generate_assignment(self, expr: Assignment) -> None:
        """Generate assignment code."""
        if not isinstance(expr.target, Identifier):
            raise CodeGenError("Complex lvalues not yet supported")

        var_name = expr.target.name

        # Resolve variable info
        if var_name in self.local_vars:
            var_info = self.local_vars[var_name]
            label = f"_{self.current_function}_{var_name}"
        elif var_name in self.globals:
            var_info = self.globals[var_name]
            label = f"_{var_name}"
        else:
            raise CodeGenError(f"Undefined variable: {var_name}")

        is_16bit = var_info["size"] == 2

        # For compound assignments, load the current value first
        if expr.op != "=":
            if is_16bit:
                self.emit(f"    SET_CD #{label}")
                self.emit(f"    LO_AB_CD")
            else:
                self.emit(f"    LOAD_A {label}")
            self.emit("    PUSH_A")
            if is_16bit:
                self.emit("    PUSH_B")

        # Evaluate RHS into A (or AB for 16-bit)
        self.generate_expression(expr.value, "A")

        # Apply compound operator
        if expr.op != "=":
            if is_16bit:
                # 16-bit compound: RHS in AB, LHS on stack
                self.emit("    AB>CD")  # move RHS to CD
                self.emit("    POP_B")  # restore LHS high byte
                self.emit("    POP_A")  # restore LHS low byte
                op_map = {
                    "+=": "AB+CD",
                    "-=": "AB-CD",
                }
                if expr.op in op_map:
                    self.emit(f"    {op_map[expr.op]}")
                else:
                    raise CodeGenError(
                        f"Unsupported compound operator for int: {expr.op}"
                    )
            else:
                # 8-bit compound: RHS in A, LHS on stack
                self.emit("    A>B")  # move RHS to B
                self.emit("    POP_A")  # restore LHS
                op_map = {
                    "+=": "ADD",
                    "-=": "SUB",
                    "&=": "AND",
                    "|=": "OR",
                    "^=": "XOR",
                }
                if expr.op in op_map:
                    self.emit(f"    {op_map[expr.op]}")
                elif expr.op in ("*=", "/=", "%="):
                    # After A>B / POP_A: A=LHS, B=RHS
                    # Need AB=(LHS,0), CD=(RHS,0)
                    self.emit("    PUSH_A")  # save LHS
                    self.emit("    0>A")
                    self.emit("    A>D")  # D = 0
                    self.emit("    B>C")  # C = RHS
                    self.emit("    0>B")  # B = 0
                    self.emit("    POP_A")  # A = LHS
                    if expr.op == "*=":
                        self.emit("    GOSUB __rt_mul")
                        self.needs_multiply = True
                    else:
                        self.emit("    GOSUB __rt_div")
                        if expr.op == "%=":
                            self.emit("    C>A")
                        self.needs_divide = True
                elif expr.op in ("<<=", ">>="):
                    # Shift: value in A, count in B
                    self.emit("    A>B")  # count (RHS) already in B... wait
                    # Actually after A>B: B=RHS, A=LHS (from POP_A)
                    # We need shift count in B and value in A — that's correct
                    shift_op = "A<<" if expr.op == "<<=" else "A>>"
                    # Generate a shift loop (reuse binary op shift logic)
                    loop_label = self.new_label(
                        "shift_left" if expr.op == "<<=" else "shift_right"
                    )
                    end_label = self.new_label("shift_end")
                    self.emit("    PUSH_A")
                    self.emit(f"{loop_label}:")
                    self.emit("    B>A")
                    self.emit("    A_ZERO")
                    self.emit(f"    JMP_ZERO {end_label}")
                    self.emit("    A>B")
                    self.emit("    POP_A")
                    self.emit(f"    {shift_op}")
                    self.emit("    PUSH_A")
                    self.emit("    B--")
                    self.emit(f"    JMP {loop_label}")
                    self.emit(f"{end_label}:")
                    self.emit("    POP_A")
                else:
                    raise CodeGenError(f"Unsupported compound operator: {expr.op}")

        # Store result
        if is_16bit:
            self.emit(f"    SET_CD #{label}")
            self.emit(f"    ST_AB_CD")
        else:
            self.emit(f"    STORE_A {label}")

    def generate_function_call(self, expr: FunctionCall) -> None:
        """Generate function call code."""
        func_params = self.function_signatures.get(expr.function, [])

        # Push stack params (3+) right-to-left so callee can pop in declaration order
        if len(expr.arguments) > 2:
            if len(expr.arguments) > len(func_params) and not func_params:
                raise CodeGenError(
                    f"Cannot determine parameter types for stack-passed arguments"
                    f" to undeclared function '{expr.function}'"
                )
            for i in range(len(expr.arguments) - 1, 1, -1):
                param_type = func_params[i].type if i < len(func_params) else None
                is_16bit = param_type and (
                    self.is_16bit_type(param_type) or self.is_pointer_type(param_type)
                )
                if is_16bit:
                    self.generate_expression(expr.arguments[i], "AB")
                    # Low byte (A) first, then high byte (B)
                    self.emit("    PUSH_A")
                    self.emit("    PUSH_B")
                else:
                    self.generate_expression(expr.arguments[i], "A")
                    self.emit("    PUSH_A")

        # Load params 1-2 into registers
        if len(expr.arguments) >= 1:
            self.generate_expression(expr.arguments[0], "A")
        if len(expr.arguments) >= 2:
            self.emit("    PUSH_A")
            self.generate_expression(expr.arguments[1], "B")
            self.emit("    POP_A")

        # Call function
        self.emit(f"    GOSUB _{expr.function}")

    # Statement code generation
    def generate_statement(self, stmt: Statement) -> None:
        """Generate code for statement."""
        if isinstance(stmt, ExpressionStatement):
            if stmt.expression:
                self.generate_expression(stmt.expression)

        elif isinstance(stmt, CompoundStatement):
            for s in stmt.statements:
                self.generate_statement(s)

        elif isinstance(stmt, ReturnStatement):
            if stmt.value:
                self.generate_expression(stmt.value, "A")
            self.emit("    RETURN")

        elif isinstance(stmt, IfStatement):
            self.generate_expression(stmt.condition, "A")
            else_label = self.new_label("else")
            end_label = self.new_label("endif")

            self.emit("    A_ZERO")
            if stmt.else_stmt:
                self.emit(f"    JMP_ZERO {else_label}")
            else:
                self.emit(f"    JMP_ZERO {end_label}")

            self.generate_statement(stmt.then_stmt)

            if stmt.else_stmt:
                self.emit(f"    JMP {end_label}")
                self.emit(f"{else_label}:")
                self.generate_statement(stmt.else_stmt)

            self.emit(f"{end_label}:")

        elif isinstance(stmt, WhileStatement):
            loop_label = self.new_label("while_loop")
            end_label = self.new_label("while_end")

            self.break_labels.append(end_label)
            self.continue_labels.append(loop_label)

            self.emit(f"{loop_label}:")
            self.generate_expression(stmt.condition, "A")
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {end_label}")
            self.generate_statement(stmt.body)
            self.emit(f"    JMP {loop_label}")
            self.emit(f"{end_label}:")

            self.break_labels.pop()
            self.continue_labels.pop()

        elif isinstance(stmt, ForStatement):
            loop_label = self.new_label("for_loop")
            continue_label = self.new_label("for_cont")
            end_label = self.new_label("for_end")

            self.break_labels.append(end_label)
            self.continue_labels.append(continue_label)

            # Init
            if stmt.init:
                self.generate_expression(stmt.init)

            self.emit(f"{loop_label}:")
            # Condition
            if stmt.condition:
                self.generate_expression(stmt.condition, "A")
                self.emit("    A_ZERO")
                self.emit(f"    JMP_ZERO {end_label}")

            # Body
            self.generate_statement(stmt.body)

            # Increment
            self.emit(f"{continue_label}:")
            if stmt.increment:
                self.generate_expression(stmt.increment)

            self.emit(f"    JMP {loop_label}")
            self.emit(f"{end_label}:")

            self.break_labels.pop()
            self.continue_labels.pop()

        elif isinstance(stmt, BreakStatement):
            if not self.break_labels:
                raise CodeGenError("break outside loop")
            self.emit(f"    JMP {self.break_labels[-1]}")

        elif isinstance(stmt, ContinueStatement):
            if not self.continue_labels:
                raise CodeGenError("continue outside loop")
            self.emit(f"    JMP {self.continue_labels[-1]}")

        elif isinstance(stmt, VariableDeclaration):
            # Local variable - allocate in function's static space
            var_name = stmt.name
            size = self.get_type_size(stmt.type)
            self.local_vars[var_name] = {"type": stmt.type, "size": size}

            # Initialize if needed
            if stmt.initializer:
                label = f"_{self.current_function}_{var_name}"
                if size == 1:
                    self.generate_expression(stmt.initializer, "A")
                    self.emit(f"    STORE_A {label}")
                else:
                    self.generate_expression(stmt.initializer, "AB")
                    self.emit(f"    SET_CD #{label}")
                    self.emit(f"    ST_AB_CD")

        else:
            raise CodeGenError(f"Unsupported statement: {type(stmt)}")

    # Top-level generation
    def generate_global_var(self, decl: VariableDeclaration) -> None:
        """Generate global variable."""
        size = self.get_type_size(decl.type)
        self.globals[decl.name] = {"type": decl.type, "size": size}

    def generate_function(self, func: FunctionDeclaration) -> None:
        """Generate function code."""
        self.current_function = func.name
        self.local_vars = {}

        # Register function parameters as local variables
        # Parameters are passed in registers, so they're implicitly available
        for param in func.parameters:
            size = self.get_type_size(param.type)
            self.local_vars[param.name] = {
                "type": param.type,
                "size": size,
                "is_param": True,
            }

        # Function label
        self.emit("")
        self.emit_comment(f"Function: {func.name}")
        self.emit(f"_{func.name}:")

        # Save parameters to static storage
        # For Phase 1: First param in A (char) or AB (int), second param in B (char) or CD (int)
        if len(func.parameters) >= 1:
            param = func.parameters[0]
            if self.is_8bit_type(param.type):
                self.emit(f"    STORE_A _{func.name}_{param.name}")
            else:
                # Save 16-bit parameter via EF pointer
                self.emit(f"    SET_EF #_{func.name}_{param.name}")
                self.emit(f"    STORE_A_EF")
                self.emit("    EF++")
                self.emit(f"    STORE_B_EF")

        if len(func.parameters) >= 2:
            param = func.parameters[1]
            if self.is_8bit_type(param.type):
                self.emit(f"    STORE_B _{func.name}_{param.name}")
            else:
                # Save CD to parameter location via EF pointer
                self.emit(f"    CD>AB")  # Move CD to AB
                self.emit(f"    SET_EF #_{func.name}_{param.name}")
                self.emit(f"    STORE_A_EF")
                self.emit("    EF++")
                self.emit(f"    STORE_B_EF")

        # Pop stack params (3+) in declaration order (caller pushed right-to-left)
        for i in range(2, len(func.parameters)):
            param = func.parameters[i]
            if self.is_8bit_type(param.type):
                self.emit(f"    POP_A")
                self.emit(f"    STORE_A _{func.name}_{param.name}")
            else:
                # Pop high byte first (B), then low byte (A) — reverse of push order
                self.emit(f"    POP_B")
                self.emit(f"    POP_A")
                self.emit(f"    SET_EF #_{func.name}_{param.name}")
                self.emit(f"    STORE_A_EF")
                self.emit("    EF++")
                self.emit(f"    STORE_B_EF")

        # Generate body
        if func.body:
            for stmt in func.body.statements:
                self.generate_statement(stmt)

            # Add implicit return if needed
            self.emit("    RETURN")

        # Save local vars for data section
        if self.local_vars:
            self.all_local_vars[func.name] = self.local_vars.copy()

    def generate_runtime_routines(self) -> None:
        """Emit software multiply/divide subroutines, only if used."""
        if self.needs_multiply:
            self.emit("")
            self.emit_comment(
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
            self.emit_comment("Software divide: A=dividend, C=divisor.")
            self.emit_comment(
                "Returns: A=quotient, C=remainder. Halts on divide by zero."
            )
            self.emit("__rt_div:")
            self.emit("    PUSH_E")
            self.emit("    PUSH_H")
            # Check for divide by zero: save A, test C, restore A
            self.emit("    A>H")  # H = dividend (save)
            self.emit("    C>A")  # A = divisor
            self.emit("    A_ZERO")  # zero flag = (divisor == 0)
            self.emit("    JMP_ZERO __rt_div_halt")
            self.emit("    H>A")  # A = dividend (restore)
            # Initialize quotient in E = 0
            self.emit("    A>H")  # H = dividend
            self.emit("    0>A")
            self.emit("    A>E")  # E = 0 (quotient)
            self.emit("    H>A")  # A = dividend
            self.emit("__rt_div_loop:")
            self.emit("    CMP_C")  # sets overflow=True if A < C
            self.emit("    JMP_OVER __rt_div_done")
            self.emit("    SUB_C")  # A = A - C
            self.emit("    A>H")  # H = remainder (save)
            self.emit("    E>A")
            self.emit("    A++")
            self.emit("    A>E")  # E = quotient + 1
            self.emit("    H>A")  # A = remainder (restore)
            self.emit("    JMP __rt_div_loop")
            self.emit("__rt_div_halt:")
            self.emit("    HALT")
            self.emit("__rt_div_done:")
            # A = remainder, E = quotient
            self.emit("    A>H")  # H = remainder
            self.emit("    E>A")  # A = quotient
            self.emit("    H>C")  # C = remainder (for % operator)
            self.emit("    POP_H")
            self.emit("    POP_E")
            self.emit("    RETURN")

    def generate_data_section(self) -> None:
        """Generate data section with variables."""
        self.emit("")
        self.emit_comment("Global variables")

        for name, info in self.globals.items():
            if info["size"] == 1:
                self.emit(f"_{name}:")
                self.emit("    .BYTE 0")
            else:
                self.emit(f"_{name}:")
                self.emit("    .WORD 0")

        # String literals
        if self.string_literals:
            self.emit("")
            self.emit_comment("String literals")
            for label, value in self.string_literals:
                # Convert escape sequences
                value = (
                    value.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
                )
                self.emit(f"{label}:")
                self.emit(f'    .ASCIIZ "{value}"')

        # Local variables (static storage)
        if self.all_local_vars:
            self.emit("")
            self.emit_comment("Static local variables")
            for func_name, local_vars in self.all_local_vars.items():
                for var_name, info in local_vars.items():
                    if info["size"] == 1:
                        self.emit(f"_{func_name}_{var_name}:")
                        self.emit("    .BYTE 0")
                    else:
                        self.emit(f"_{func_name}_{var_name}:")
                        self.emit("    .WORD 0")

    def generate(self, program: Program) -> str:
        """Generate assembly code from AST."""
        self.emit("; Generated by SK02-C compiler")
        self.emit(".ORG $8000")
        self.emit("")
        self.emit("; Entry point")
        self.emit("    JMP _main")
        self.emit("")

        # First pass: collect global variables and function signatures
        for decl in program.declarations:
            if isinstance(decl, VariableDeclaration):
                self.generate_global_var(decl)
            elif isinstance(decl, FunctionDeclaration):
                self.function_signatures[decl.name] = decl.parameters

        # Generate functions
        for decl in program.declarations:
            if isinstance(decl, FunctionDeclaration):
                self.generate_function(decl)

        # Emit runtime subroutines (only if used)
        self.generate_runtime_routines()

        # Generate data section
        self.generate_data_section()

        return "\n".join(self.output)
