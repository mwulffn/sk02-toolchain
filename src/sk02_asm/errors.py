"""Error handling for the SK-02 assembler."""


class AssemblyError(Exception):
    """Base exception for assembly errors."""

    def __init__(
        self, message: str, line_num: int | None = None, line: str | None = None
    ):
        self.message = message
        self.line_num = line_num
        self.line = line
        super().__init__(self._format_error())

    def _format_error(self) -> str:
        """Format error message with line information."""
        if self.line_num is not None:
            msg = f"Line {self.line_num}: {self.message}"
            if self.line:
                msg += f"\n  {self.line}"
            return msg
        return self.message


class AsmSyntaxError(AssemblyError):
    """Syntax error in assembly source."""

    pass


# Backwards-compatible alias — do not use in new code.
SyntaxError = AsmSyntaxError


class UndefinedSymbolError(AssemblyError):
    """Reference to undefined symbol/label."""

    pass


class DuplicateSymbolError(AssemblyError):
    """Duplicate symbol definition."""

    pass


class InvalidOpcodeError(AssemblyError):
    """Invalid or unknown opcode."""

    pass


class InvalidOperandError(AssemblyError):
    """Invalid operand for instruction."""

    pass


class AddressOutOfRangeError(AssemblyError):
    """Address exceeds valid range."""

    pass
