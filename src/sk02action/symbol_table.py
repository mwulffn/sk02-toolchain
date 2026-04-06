"""Symbol table for the SK-02 Action! compiler.

Two-scope design: global scope + one function-local scope at a time.
"""

from .ast_nodes import Type


class SymbolTable:
    """Tracks variable and function declarations with global/local scoping."""

    def __init__(self):
        self._globals: dict[str, dict] = {}
        self._locals: dict[str, dict] | None = None
        self._functions: dict[str, dict] = {}
        self._current_scope: str | None = None

    def enter_scope(self, name: str) -> None:
        """Enter a function/procedure scope."""
        self._current_scope = name
        self._locals = {}

    def exit_scope(self) -> None:
        """Exit the current function/procedure scope."""
        self._current_scope = None
        self._locals = None

    @property
    def in_scope(self) -> bool:
        return self._locals is not None

    @property
    def scope_name(self) -> str | None:
        return self._current_scope

    def declare_var(
        self,
        name: str,
        var_type: Type,
        *,
        size: int,
        address: int | None = None,
        initial_value: int | None = None,
    ) -> None:
        """Declare a variable in the current scope (local if in scope, else global)."""
        info = {
            "type": var_type,
            "size": size,
            "address": address,
            "initial_value": initial_value,
        }
        if self._locals is not None:
            self._locals[name] = info
        else:
            self._globals[name] = info

    def resolve(self, name: str) -> dict | None:
        """Resolve a variable name, checking local scope first."""
        if self._locals is not None and name in self._locals:
            return self._locals[name]
        if name in self._globals:
            return self._globals[name]
        return None

    def declare_func(
        self,
        name: str,
        *,
        params: list[dict],
        return_type: Type | None,
    ) -> None:
        """Declare a function or procedure."""
        self._functions[name] = {
            "params": params,
            "return_type": return_type,
        }

    def resolve_func(self, name: str) -> dict | None:
        """Resolve a function/procedure name."""
        return self._functions.get(name)

    @property
    def globals(self) -> dict[str, dict]:
        return self._globals

    @property
    def functions(self) -> dict[str, dict]:
        return self._functions
