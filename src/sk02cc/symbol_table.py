"""Symbol table for SK02-C codegen.

Tracks global variables, per-function local variables (including parameters),
and function signatures.  Provides ``resolve_var`` which maps a name to the
assembly label and var_info dict used throughout codegen.
"""

from .ast_nodes import Parameter, Type
from .codegen_errors import CodeGenError

VarInfo = dict  # {"type": Type, "size": int, "is_param"?: bool}


class SymbolTable:
    """Two-scope symbol table: globals and one active function frame."""

    def __init__(self):
        self.globals: dict[str, VarInfo] = {}
        self.local_vars: dict[str, VarInfo] = {}
        self.all_local_vars: dict[str, dict[str, VarInfo]] = {}
        self.function_signatures: dict[str, list[Parameter]] = {}
        self.current_function: str | None = None

    # ------------------------------------------------------------------
    # Declaration
    # ------------------------------------------------------------------

    def declare_global(self, name: str, typ: Type, size: int) -> None:
        self.globals[name] = {"type": typ, "size": size}

    def enter_function(self, func_name: str) -> None:
        self.current_function = func_name
        self.local_vars = {}

    def declare_local(
        self, name: str, typ: Type, size: int, is_param: bool = False
    ) -> None:
        info: VarInfo = {"type": typ, "size": size}
        if is_param:
            info["is_param"] = True
        self.local_vars[name] = info

    def exit_function(self) -> None:
        if self.local_vars:
            self.all_local_vars[self.current_function] = self.local_vars.copy()
        self.local_vars = {}
        self.current_function = None

    def register_function(self, name: str, params: list[Parameter]) -> None:
        self.function_signatures[name] = params

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def resolve_var(self, name: str) -> tuple[str, VarInfo]:
        """Return (assembly label, var_info) for *name*.

        Checks local scope first, then globals.
        Raises CodeGenError if the name is undeclared.
        """
        if name in self.local_vars:
            label = f"_{self.current_function}_{name}"
            return label, self.local_vars[name]
        if name in self.globals:
            label = f"_{name}"
            return label, self.globals[name]
        raise CodeGenError(f"Undefined variable: {name}")
