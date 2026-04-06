"""Code generator for SK02-C compiler."""

from .ast_nodes import *
from .calling_convention import CallingConvention
from .codegen_errors import CodeGenError
from .emitter import Emitter
from .symbol_table import SymbolTable


class CodeGenerator:
    """Generate SK-02 assembly from AST."""

    def __init__(self):
        self._em = Emitter()
        self._syms = SymbolTable()
        self._cc = CallingConvention(
            self._em, self.generate_expression, self._syms.function_signatures
        )
        self.string_literals = []
        self.break_labels = []
        self.continue_labels = []
        self.needs_multiply = False  # emit __rt_mul subroutine if True
        self.needs_divide = False  # emit __rt_div subroutine if True

    # ------------------------------------------------------------------
    # Convenience delegates
    # ------------------------------------------------------------------

    def emit(self, line: str) -> None:
        self._em.emit(line)

    def emit_comment(self, comment: str) -> None:
        self._em.emit_comment(comment)

    def new_label(self, prefix: str = "L") -> str:
        return self._em.new_label(prefix)

    def resolve_var(self, name: str) -> tuple[str, dict]:
        return self._syms.resolve_var(name)

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------

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
        return isinstance(typ, BasicType) and typ.name in ("char", "uint8", "int8")

    def is_16bit_type(self, typ: Type) -> bool:
        return isinstance(typ, BasicType) and typ.name in ("int", "uint16", "int16")

    def is_signed_type(self, typ: Type) -> bool:
        return isinstance(typ, BasicType) and typ.name in ("int8", "int16", "int")

    def is_pointer_type(self, typ: Type) -> bool:
        return isinstance(typ, PointerType)

    def _zero_storage_directive(self, typ: Type, size: int) -> str:
        """Return a .BYTE or .WORD directive string with zero-initialised storage."""
        if isinstance(typ, ArrayType):
            if not typ.size:
                raise CodeGenError("Zero-length arrays are not supported")
            elem_size = self.get_type_size(typ.base_type)
            count = typ.size
            if elem_size == 1:
                return ".BYTE " + ", ".join(["0"] * count)
            else:
                return ".WORD " + ", ".join(["0"] * count)
        if size == 1:
            return ".BYTE 0"
        return ".WORD 0"

    # ------------------------------------------------------------------
    # Expression code generation
    # ------------------------------------------------------------------

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
            label, var_info = self.resolve_var(expr.name)
            if isinstance(var_info["type"], ArrayType):
                # Array name decays to pointer — emit base address into the
                # requested wide register (AB or CD) so callers that need the
                # address in CD (e.g. second pointer argument) work correctly.
                target_reg = result_reg if result_reg in ("AB", "CD", "EF", "GH") else "AB"
                self.emit(f"    SET_{target_reg} #{label}")
            elif var_info["size"] == 1:
                self.emit(f"    LOAD_A {label}")
            else:
                # Load 16-bit value via CD pointer
                self.emit(f"    SET_CD #{label}")
                self.emit("    LO_AB_CD")

        elif isinstance(expr, BinaryOp):
            self.generate_binary_op(expr)

        elif isinstance(expr, UnaryOp):
            self.generate_unary_op(expr)

        elif isinstance(expr, Assignment):
            self.generate_assignment(expr)

        elif isinstance(expr, FunctionCall):
            self._cc.emit_call(expr)

        elif isinstance(expr, StringLiteral):
            # Add to string literals and generate reference
            str_label = f"_str{len(self.string_literals)}"
            self.string_literals.append((str_label, expr.value))
            self.emit(f"    SET_AB #{str_label}")

        elif isinstance(expr, ArrayAccess):
            self._generate_array_access_read(expr, result_reg)

        else:
            raise CodeGenError(f"Unsupported expression: {type(expr)}")

    def generate_binary_op(self, expr: BinaryOp) -> None:
        """Generate code for binary operation."""
        # && and || require short-circuit evaluation — handle before the
        # eager evaluate-both-sides pattern below.
        if expr.op in ("&&", "||"):
            self.generate_logical_op(expr)
            return

        # Evaluate left operand; result is in A (8-bit) or AB (16-bit).
        self.generate_expression(expr.left, "A")
        left_type = expr.left.resolved_type
        is_16bit = left_type is not None and self.is_16bit_type(left_type)

        if is_16bit:
            # Preserve both bytes of the 16-bit left operand.
            self.emit("    PUSH_A")  # push low byte
            self.emit("    PUSH_B")  # push high byte
        else:
            self.emit("    PUSH_A")

        # Evaluate right operand; result is in A (8-bit) or AB (16-bit).
        self.generate_expression(expr.right, "B")
        right_type = expr.right.resolved_type

        if is_16bit:
            # Move right operand from AB to CD; restore left into AB.
            self.emit("    AB>CD")
            self.emit("    POP_B")  # restore left's high byte
            self.emit("    POP_A")  # restore left's low byte
        else:
            # For 8-bit: move RHS from A to B (unless it was already there).
            if not isinstance(expr.right, (NumberLiteral, CharLiteral)):
                self.emit("    A>B")
            self.emit("    POP_A")

        if expr.op == "+":
            if is_16bit:
                self.emit("    AB+CD")  # AB = AB + CD
            else:
                self.emit("    ADD")  # A = A + B
        elif expr.op == "-":
            if is_16bit:
                self.emit("    AB-CD")  # AB = AB - CD
            else:
                self.emit("    SUB")  # A = A - B
        elif expr.op == "&":
            self.emit("    AND")
        elif expr.op == "|":
            self.emit("    OR")
        elif expr.op == "^":
            self.emit("    XOR")
        elif expr.op == "<<":
            # Shift A (or AB) left by B times using a loop.
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
            # Shift A right by B times. Use arithmetic (sign-extending) shift
            # for signed types, logical shift for unsigned types.
            is_signed_shift = left_type is not None and self.is_signed_type(left_type)
            shift_instr = "S_A>>" if is_signed_shift else "A>>"
            loop_label = self.new_label("shift_right")
            end_label = self.new_label("shift_end")
            self.emit("    PUSH_A")  # Save value to shift
            self.emit(f"{loop_label}:")
            self.emit("    B>A")  # Move B to A to test
            self.emit("    A_ZERO")
            self.emit(f"    JMP_ZERO {end_label}")
            self.emit("    A>B")  # Move back
            self.emit("    POP_A")  # Get value
            self.emit(f"    {shift_instr}")
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
                self.generate_signed_comparison(expr.op, is_16bit=is_16bit)
            else:
                self.generate_comparison(expr.op, is_16bit=is_16bit)
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

    def generate_comparison(self, op: str, is_16bit: bool = False) -> None:
        """Generate comparison code.

        CMP / CMP_16 sets flags without modifying registers:
          overflow = (A - B) < 0  →  overflow is SET when A < B (unsigned)
          zero     = (A - B) == 0 →  zero is SET when A == B

        For 16-bit, CMP_16 compares AB vs CD using the same flag semantics.

        Derived conditions:
          A <  B  →  overflow set,   zero clear
          A == B  →  overflow clear, zero set
          A >  B  →  overflow clear, zero clear
          A >= B  →  overflow clear  (zero may or may not be set)
          A <= B  →  overflow set OR zero set
        """
        self.emit("    CMP_16" if is_16bit else "    CMP")
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

    def generate_signed_comparison(self, op: str, is_16bit: bool = False) -> None:
        """Generate signed comparison using sign-bit checks before CMP/CMP_16.

        8-bit:  A = left,  B = right.  Sign bit in A's MSB / B's MSB.
        16-bit: AB = left, CD = right. Sign bit in B's MSB (high byte of AB)
                                       / D's MSB (high byte of CD).

        Algorithm:
          1. Check sign of left operand.
             8-bit: JMP_A_POS; 16-bit: JMP_B_POS
          2. Left is negative: check right.
             8-bit: JMP_B_POS; 16-bit: copy D to A, JMP_A_POS
          3. If different signs → result is determined (neg < pos).
          4. If same sign → CMP/CMP_16 gives correct unsigned ordering.
        """
        a_pos = self.new_label("sgn_a_pos")
        diff_a_neg = self.new_label("sgn_diff_a_neg")  # left neg, right pos: left < right
        diff_a_pos = self.new_label("sgn_diff_a_pos")  # left pos, right neg: left > right
        same_sign = self.new_label("sgn_same")
        true_label = self.new_label("sgn_true")
        false_label = self.new_label("sgn_false")
        end_label = self.new_label("sgn_end")

        if is_16bit:
            # Sign of left is B's MSB (high byte of AB).
            # Sign of right is D's MSB (high byte of CD) — copy D→A to test.
            self.emit(f"    JMP_B_POS {a_pos}")          # left non-negative
            # Left negative: check right's high byte
            self.emit("    D>A")
            self.emit(f"    JMP_A_POS {diff_a_neg}")     # right positive → left < right
            self.emit(f"    JMP {same_sign}")             # both negative

            self.emit(f"{a_pos}:")
            # Left non-negative: check right's high byte
            self.emit("    D>A")
            self.emit(f"    JMP_A_POS {same_sign}")      # both positive
            self.emit(f"    JMP {diff_a_pos}")            # left pos, right neg
        else:
            # 8-bit: sign of left is A's MSB, sign of right is B's MSB.
            self.emit(f"    JMP_A_POS {a_pos}")
            # A negative: check B
            self.emit(f"    JMP_B_POS {diff_a_neg}")     # B positive → A < B
            self.emit(f"    JMP {same_sign}")             # both negative

            self.emit(f"{a_pos}:")
            # A non-negative: check B
            self.emit(f"    JMP_B_POS {same_sign}")      # both positive
            self.emit(f"    JMP {diff_a_pos}")

        # Left < right case (left neg, right pos)
        self.emit(f"{diff_a_neg}:")
        if op in ("<", "<="):
            self.emit(f"    JMP {true_label}")
        else:
            self.emit(f"    JMP {false_label}")

        # Left > right case (left pos, right neg)
        self.emit(f"{diff_a_pos}:")
        if op in (">", ">="):
            self.emit(f"    JMP {true_label}")
        else:
            self.emit(f"    JMP {false_label}")

        # Same-sign: CMP/CMP_16 gives correct signed ordering
        self.emit(f"{same_sign}:")
        self.emit("    CMP_16" if is_16bit else "    CMP")
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

    def _generate_inc_dec(
        self, label: str, size: int, is_increment: bool, postfix: bool
    ) -> None:
        """Emit increment or decrement for a variable at the given label.

        Works for both 8-bit (size=1) and 16-bit (size=2) variables and
        supports prefix and postfix semantics.  Result left in A (8-bit)
        or AB (16-bit).
        """
        if size == 1:
            self.emit(f"    LOAD_A {label}")
            if postfix:
                self.emit("    PUSH_A")
            self.emit("    A++" if is_increment else "    A--")
            self.emit(f"    STORE_A {label}")
            if postfix:
                self.emit("    POP_A")
        else:
            self.emit(f"    SET_CD #{label}")
            self.emit("    LO_AB_CD")
            if postfix:
                self.emit("    PUSH_A")
                self.emit("    PUSH_B")
            self.emit("    AB++" if is_increment else "    AB--")
            self.emit(f"    SET_CD #{label}")
            self.emit("    ST_AB_CD")
            if postfix:
                self.emit("    POP_B")
                self.emit("    POP_A")

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
            if not isinstance(expr.operand, Identifier):
                raise CodeGenError("++ only supported for variables")
            label, var_info = self.resolve_var(expr.operand.name)
            self._generate_inc_dec(label, var_info["size"], is_increment=True, postfix=expr.postfix)
        elif expr.op == "--":
            if not isinstance(expr.operand, Identifier):
                raise CodeGenError("-- only supported for variables")
            label, var_info = self.resolve_var(expr.operand.name)
            self._generate_inc_dec(label, var_info["size"], is_increment=False, postfix=expr.postfix)
        elif expr.op == "&":
            # Address-of: produce the variable's static address in AB
            if not isinstance(expr.operand, Identifier):
                raise CodeGenError("Address-of requires a variable")
            label, _ = self.resolve_var(expr.operand.name)
            self.emit(f"    SET_AB #{label}")

        elif expr.op == "*":
            # Dereference: load value at the address held in the pointer
            self.generate_expression(expr.operand, "A")
            ptr_type = expr.operand.resolved_type
            if not isinstance(ptr_type, PointerType):
                raise CodeGenError("Dereference of non-pointer type")
            pointee_type = ptr_type.base_type
            self.emit("    AB>CD")
            if self.is_8bit_type(pointee_type):
                self.emit("    LOAD_A_CD")
            else:
                self.emit("    LO_AB_CD")

        else:
            raise CodeGenError(f"Unsupported unary operator: {expr.op}")

    def _generate_deref_assignment(self, expr: Assignment) -> None:
        """Generate assignment through a dereferenced pointer (*ptr = value)."""
        if expr.op != "=":
            raise CodeGenError("Compound assignment through pointer not yet supported")
        # Evaluate pointer expression — address lands in AB
        self.generate_expression(expr.target.operand, "A")
        ptr_type = expr.target.operand.resolved_type
        if not isinstance(ptr_type, PointerType):
            raise CodeGenError("Dereference of non-pointer type")
        pointee_type = ptr_type.base_type
        # Park pointer address in GH while we evaluate the RHS.
        # GH is not used by any expression evaluation code paths, so it is safe.
        self.emit("    AB>GH")
        if self.is_8bit_type(pointee_type):
            self.generate_expression(expr.value, "A")
            self.emit("    STORE_A_GH")
        else:
            self.generate_expression(expr.value, "AB")
            self.emit("    STORE_A_GH")
            self.emit("    GH++")
            self.emit("    STORE_B_GH")

    def _emit_array_base(self, array_expr: "Expression") -> None:
        """Load array base address into AB. May use CD as scratch."""
        if (
            isinstance(array_expr, Identifier)
            and isinstance(array_expr.resolved_type, ArrayType)
        ):
            label, _ = self.resolve_var(array_expr.name)
            self.emit(f"    SET_AB #{label}")
        else:
            # Pointer expression — evaluate to get the pointer value into AB
            self.generate_expression(array_expr, "AB")

    def _compute_array_address(self, expr: ArrayAccess) -> None:
        """Compute array element address into AB."""
        elem_type = expr.resolved_type
        elem_size = self.get_type_size(elem_type)

        if isinstance(expr.index, NumberLiteral):
            # Constant index: base + compile-time byte offset
            byte_offset = expr.index.value * elem_size
            self._emit_array_base(expr.array)
            if byte_offset > 0:
                self.emit(f"    SET_CD #{byte_offset}")
                self.emit("    AB+CD")
        else:
            # Evaluate and scale the index first — index evaluation may freely use CD.
            # For 8-bit: zero-extend to 16-bit BEFORE shifting to preserve carry.
            idx_type = expr.index.resolved_type
            if self.is_8bit_type(idx_type):
                self.generate_expression(expr.index, "A")
                self.emit("    0>B")       # zero-extend first (preserves carry on shift)
                if elem_size == 2:
                    self.emit("    AB<<")  # scale ×2 as 16-bit
            else:
                self.generate_expression(expr.index, "AB")
                if elem_size == 2:
                    self.emit("    AB<<")  # scale ×2
            # Push scaled index, compute base into CD, pop index, add.
            # This protects the index from CD clobber during base evaluation.
            self.emit("    PUSH_A")
            self.emit("    PUSH_B")
            self._emit_array_base(expr.array)  # base into AB (uses CD freely)
            self.emit("    AB>CD")
            self.emit("    POP_B")
            self.emit("    POP_A")
            self.emit("    AB+CD")   # AB = scaled_index + base

    def _generate_array_access_read(self, expr: ArrayAccess, result_reg: str = "A") -> None:
        """Generate a read from arr[i] into result_reg."""
        self._compute_array_address(expr)
        elem_type = expr.resolved_type
        self.emit("    AB>CD")
        if self.is_8bit_type(elem_type):
            self.emit("    LOAD_A_CD")
            # Move to requested single-byte register if not A
            if result_reg == "B":
                self.emit("    A>B")
            elif result_reg not in ("A", "AB"):
                self.emit(f"    A>{result_reg}")
        else:
            self.emit("    LO_AB_CD")

    def _generate_array_access_write(self, expr: Assignment) -> None:
        """Generate a write to arr[i] = value, or a compound arr[i] op= value."""
        target = expr.target
        if not isinstance(target, ArrayAccess):
            raise CodeGenError("Expected ArrayAccess target")
        self._compute_array_address(target)
        # Park address in GH — safe; no expression evaluation touches GH.
        self.emit("    AB>GH")
        elem_type = target.resolved_type
        is_8bit = self.is_8bit_type(elem_type)

        if expr.op != "=":
            # Compound: read current element value, push as LHS, eval RHS, apply op.
            if is_8bit:
                self.emit("    GH>AB")
                self.emit("    AB>CD")
                self.emit("    LOAD_A_CD")   # current value → A
                self.emit("    PUSH_A")       # save LHS
                self.generate_expression(expr.value, "A")   # RHS → A
                self.emit("    A>B")          # RHS → B
                self.emit("    POP_A")        # LHS → A
                op_map_8 = {
                    "+=": "ADD", "-=": "SUB",
                    "&=": "AND", "|=": "OR", "^=": "XOR",
                }
                if expr.op in op_map_8:
                    self.emit(f"    {op_map_8[expr.op]}")
                else:
                    raise CodeGenError(
                        f"Unsupported compound operator for array element: {expr.op}"
                    )
                self.emit("    STORE_A_GH")
            else:
                # 16-bit compound
                self.emit("    GH>AB")
                self.emit("    AB>CD")
                self.emit("    LO_AB_CD")    # current value → AB
                self.emit("    PUSH_A")
                self.emit("    PUSH_B")      # save LHS (16-bit)
                self.generate_expression(expr.value, "AB")  # RHS → AB
                self.emit("    AB>CD")       # RHS → CD
                self.emit("    POP_B")
                self.emit("    POP_A")       # LHS → AB
                op_map_16 = {"+=": "AB+CD", "-=": "AB-CD"}
                if expr.op in op_map_16:
                    self.emit(f"    {op_map_16[expr.op]}")
                else:
                    raise CodeGenError(
                        f"Unsupported compound operator for 16-bit array element: {expr.op}"
                    )
                self.emit("    STORE_A_GH")
                self.emit("    GH++")
                self.emit("    STORE_B_GH")
        else:
            # Simple assignment
            if is_8bit:
                self.generate_expression(expr.value, "A")
                self.emit("    STORE_A_GH")
            else:
                self.generate_expression(expr.value, "AB")
                self.emit("    STORE_A_GH")
                self.emit("    GH++")
                self.emit("    STORE_B_GH")

    def generate_assignment(self, expr: Assignment) -> None:
        """Generate assignment code."""
        if isinstance(expr.target, UnaryOp) and expr.target.op == "*":
            self._generate_deref_assignment(expr)
            return
        if isinstance(expr.target, ArrayAccess):
            self._generate_array_access_write(expr)
            return
        if not isinstance(expr.target, Identifier):
            raise CodeGenError("Complex lvalues not yet supported")

        label, var_info = self.resolve_var(expr.target.name)
        if isinstance(var_info["type"], ArrayType):
            raise CodeGenError("Cannot assign to an array variable")

        is_16bit = var_info["size"] == 2

        # For compound assignments, load the current value first
        if expr.op != "=":
            if is_16bit:
                self.emit(f"    SET_CD #{label}")
                self.emit("    LO_AB_CD")
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
                    # After A>B / POP_A above: A=LHS (value), B=RHS (count).
                    # Shift loop needs value in A and count in B — already correct.
                    is_signed_shift = self.is_signed_type(var_info["type"])
                    if expr.op == "<<=":
                        shift_op = "A<<"
                    elif is_signed_shift:
                        shift_op = "S_A>>"
                    else:
                        shift_op = "A>>"
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
            self.emit("    ST_AB_CD")
        else:
            self.emit(f"    STORE_A {label}")

    # ------------------------------------------------------------------
    # Statement code generation
    # ------------------------------------------------------------------

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
            size = self.get_type_size(stmt.type)
            self._syms.declare_local(stmt.name, stmt.type, size)

            # Initialize if needed
            if stmt.initializer:
                label = f"_{self._syms.current_function}_{stmt.name}"
                if size == 1:
                    self.generate_expression(stmt.initializer, "A")
                    self.emit(f"    STORE_A {label}")
                else:
                    self.generate_expression(stmt.initializer, "AB")
                    self.emit(f"    SET_CD #{label}")
                    self.emit("    ST_AB_CD")

        else:
            raise CodeGenError(f"Unsupported statement: {type(stmt)}")

    # ------------------------------------------------------------------
    # Top-level generation
    # ------------------------------------------------------------------

    def generate_function(self, func: FunctionDeclaration) -> None:
        """Generate function code."""
        self._syms.enter_function(func.name)

        # Register parameters in local scope
        for param in func.parameters:
            size = self.get_type_size(param.type)
            self._syms.declare_local(param.name, param.type, size, is_param=True)

        # Function label
        self.emit("")
        self.emit_comment(f"Function: {func.name}")
        self.emit(f"_{func.name}:")

        # Save incoming register/stack parameters to static storage
        self._cc.emit_param_saves(func)

        # Generate body
        if func.body:
            for stmt in func.body.statements:
                self.generate_statement(stmt)
            self.emit("    RETURN")

        self._syms.exit_function()

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
            self.emit("    A>H")  # H = dividend (save)
            self.emit("    C>A")  # A = divisor
            self.emit("    A_ZERO")  # zero flag = (divisor == 0)
            self.emit("    JMP_ZERO __rt_div_halt")
            self.emit("    H>A")  # A = dividend (restore)
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

        for name, info in self._syms.globals.items():
            self.emit(f"_{name}:")
            directive = self._zero_storage_directive(info["type"], info["size"])
            self.emit(f"    {directive}")

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
        if self._syms.all_local_vars:
            self.emit("")
            self.emit_comment("Static local variables")
            for func_name, local_vars in self._syms.all_local_vars.items():
                for var_name, info in local_vars.items():
                    self.emit(f"_{func_name}_{var_name}:")
                    directive = self._zero_storage_directive(info["type"], info["size"])
                    self.emit(f"    {directive}")

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
                size = self.get_type_size(decl.type)
                self._syms.declare_global(decl.name, decl.type, size)
            elif isinstance(decl, FunctionDeclaration):
                self._syms.register_function(decl.name, decl.parameters)

        # Generate functions
        for decl in program.declarations:
            if isinstance(decl, FunctionDeclaration):
                self.generate_function(decl)

        # Emit runtime subroutines (only if used)
        self.generate_runtime_routines()

        # Generate data section
        self.generate_data_section()

        return self._em.get_output()
