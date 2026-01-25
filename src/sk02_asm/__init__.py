"""SK-02 8-bit Computer Assembler."""

from .assembler import Assembler, assemble_file
from .errors import AssemblyError
from .opcodes import OPCODES, OperandType, get_opcode
from .symbols import SymbolTable

__version__ = "0.1.0"

__all__ = [
    "Assembler",
    "assemble_file",
    "AssemblyError",
    "OPCODES",
    "get_opcode",
    "OperandType",
    "SymbolTable",
]
