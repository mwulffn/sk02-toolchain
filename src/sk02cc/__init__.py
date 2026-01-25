"""SK02-C Compiler - C subset compiler for the SK-02 8-bit computer."""

from .compiler import compile_file, compile_string

__all__ = ["compile_file", "compile_string"]
__version__ = "0.1.0"
