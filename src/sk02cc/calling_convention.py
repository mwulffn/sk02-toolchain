"""SK-02 calling convention: parameter passing and return values.

Calling convention (SK-02 C subset):
  - Param 1: register A (8-bit) or AB (16-bit/pointer)
  - Param 2: register B (8-bit) or CD (16-bit/pointer)
              When param 1 is 16-bit and param 2 is 8-bit, param 2 is
              temporarily parked in C by the caller.
  - Params 3+: pushed onto the data stack right-to-left by caller;
               popped left-to-right (declaration order) by callee.
  - Return value: register A (8-bit) or AB (16-bit)
  - Functions invoked with GOSUB / RETURN.

This module provides two helpers used by CodeGenerator:
  - ``emit_call``    — caller side: evaluate and pass arguments, then GOSUB
  - ``emit_param_saves`` — callee side: save register/stack params to static storage
"""

from __future__ import annotations

from typing import Callable

from .ast_nodes import FunctionCall, FunctionDeclaration, Parameter, Type
from .codegen_errors import CodeGenError
from .emitter import Emitter

# Type alias for the generate_expression callback
_GenExprFn = Callable[[object, str], None]  # (expr, result_reg) -> None


def _is_wide(typ: Type | None) -> bool:
    """Return True for types that occupy two bytes (16-bit or pointer)."""
    if typ is None:
        return False
    from .ast_nodes import BasicType, PointerType

    if isinstance(typ, PointerType):
        return True
    if isinstance(typ, BasicType):
        return typ.name in ("int", "uint16", "int16")
    return False


class CallingConvention:
    """Implements the SK-02 C calling convention for codegen."""

    def __init__(
        self,
        emitter: Emitter,
        generate_expr: _GenExprFn,
        function_signatures: dict[str, list[Parameter]],
    ):
        self._em = emitter
        self._gen = generate_expr
        self._sigs = function_signatures

    # ------------------------------------------------------------------
    # Caller side
    # ------------------------------------------------------------------

    def emit_call(self, expr: FunctionCall) -> None:
        """Evaluate arguments according to the calling convention, then GOSUB."""
        func_params = self._sigs.get(expr.function, [])
        args = expr.arguments

        # --- Stack-passed params (index 2+): push right-to-left ---
        if len(args) > 2:
            if not func_params:
                raise CodeGenError(
                    f"Cannot determine parameter types for stack-passed arguments"
                    f" to undeclared function '{expr.function}'"
                )
            for i in range(len(args) - 1, 1, -1):
                param_type = func_params[i].type if i < len(func_params) else None
                if _is_wide(param_type):
                    self._gen(args[i], "AB")
                    self._em.emit("    PUSH_A")
                    self._em.emit("    PUSH_B")
                else:
                    self._gen(args[i], "A")
                    self._em.emit("    PUSH_A")

        # --- Register params (index 0 and 1) ---
        param1_type = func_params[0].type if func_params else None
        param1_wide = _is_wide(param1_type)

        if len(args) >= 2 and param1_wide:
            param2_type = func_params[1].type if len(func_params) > 1 else None
            if param2_type and not _is_wide(param2_type):
                # Conflict: param 1 needs AB, param 2 needs B.
                # Park param 2 in C, then load param 1 into AB.
                self._gen(args[1], "A")
                self._em.emit("    A>C")
                self._gen(args[0], "A")
            else:
                # Both wide: param1 → AB, param2 → CD.
                # Save both bytes of param1, evaluate param2 into AB, move to CD,
                # then restore param1 into AB.
                self._gen(args[0], "A")
                self._em.emit("    PUSH_A")
                self._em.emit("    PUSH_B")
                self._gen(args[1], "AB")
                self._em.emit("    AB>CD")
                self._em.emit("    POP_B")
                self._em.emit("    POP_A")
        else:
            if len(args) >= 1:
                self._gen(args[0], "A")
            if len(args) >= 2:
                param2_type = func_params[1].type if len(func_params) > 1 else None
                self._em.emit("    PUSH_A")
                if _is_wide(param2_type):
                    # Wide param2 goes in CD: evaluate into AB, move to CD.
                    # Narrow param1 evaluation cannot touch CD, so this is safe.
                    self._gen(args[1], "AB")
                    self._em.emit("    AB>CD")
                else:
                    self._gen(args[1], "B")
                self._em.emit("    POP_A")

        self._em.emit(f"    GOSUB _{expr.function}")

    # ------------------------------------------------------------------
    # Callee side
    # ------------------------------------------------------------------

    def emit_param_saves(self, func: FunctionDeclaration) -> None:
        """Emit prologue instructions that save register/stack params to static storage."""
        params = func.parameters
        name = func.name

        if len(params) >= 1:
            p = params[0]
            if not _is_wide(p.type):
                self._em.emit(f"    STORE_A _{name}_{p.name}")
            else:
                self._em.emit(f"    SET_EF #_{name}_{p.name}")
                self._em.emit("    STORE_A_EF")
                self._em.emit("    EF++")
                self._em.emit("    STORE_B_EF")

        if len(params) >= 2:
            p = params[1]
            param0_wide = _is_wide(params[0].type)
            if not _is_wide(p.type):
                if param0_wide:
                    # Caller parked param 2 in C to avoid AB conflict.
                    self._em.emit("    C>A")
                    self._em.emit(f"    STORE_A _{name}_{p.name}")
                else:
                    self._em.emit(f"    STORE_B _{name}_{p.name}")
            else:
                self._em.emit("    CD>AB")
                self._em.emit(f"    SET_EF #_{name}_{p.name}")
                self._em.emit("    STORE_A_EF")
                self._em.emit("    EF++")
                self._em.emit("    STORE_B_EF")

        # Stack-passed params (index 2+): pop in declaration order.
        for i in range(2, len(params)):
            p = params[i]
            if not _is_wide(p.type):
                self._em.emit("    POP_A")
                self._em.emit(f"    STORE_A _{name}_{p.name}")
            else:
                self._em.emit("    POP_B")
                self._em.emit("    POP_A")
                self._em.emit(f"    SET_EF #_{name}_{p.name}")
                self._em.emit("    STORE_A_EF")
                self._em.emit("    EF++")
                self._em.emit("    STORE_B_EF")
