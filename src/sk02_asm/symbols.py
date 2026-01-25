"""Symbol table for labels and constants."""

from .errors import DuplicateSymbolError, UndefinedSymbolError


class SymbolTable:
    """Manages labels and constants with local label scoping."""

    def __init__(self):
        self.symbols: dict[str, int] = {}
        self.current_global_label: str | None = None

    def define(self, name: str, value: int, line_num: int | None = None):
        """Define a symbol."""
        # Handle local labels (.label)
        if name.startswith("."):
            if self.current_global_label is None:
                raise DuplicateSymbolError(
                    "Local label must follow a global label", line_num
                )
            # Create scoped name: global.local
            full_name = f"{self.current_global_label}{name}"
        else:
            # Global label - update current scope
            full_name = name
            self.current_global_label = name

        # Check for duplicates
        if full_name in self.symbols:
            raise DuplicateSymbolError(f"Duplicate symbol: {name}", line_num)

        self.symbols[full_name] = value

    def lookup(self, name: str) -> int:
        """Look up a symbol value."""
        # Handle local labels
        if name.startswith("."):
            if self.current_global_label is None:
                raise UndefinedSymbolError(f"Undefined symbol: {name}")
            full_name = f"{self.current_global_label}{name}"
        else:
            full_name = name

        if full_name not in self.symbols:
            raise UndefinedSymbolError(f"Undefined symbol: {name}")

        return self.symbols[full_name]

    def contains(self, name: str) -> bool:
        """Check if a symbol exists."""
        try:
            self.lookup(name)
            return True
        except UndefinedSymbolError:
            return False

    def set_global_scope(self, label: str):
        """Set the current global label scope."""
        if not label.startswith("."):
            self.current_global_label = label

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"SymbolTable({self.symbols})"
