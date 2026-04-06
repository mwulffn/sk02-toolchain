"""Main compiler module for SK-02 Action!."""

from pathlib import Path

from .call_graph import CallGraph
from .codegen import CodeGenerator
from .const_fold import ConstantFolder
from .lexer import Lexer
from .parser import Parser
from .type_checker import TypeChecker


def compile_string(source: str, *, origin: int = 0x8000) -> str:
    """Compile Action! source code to SK-02 assembly.

    Args:
        source: Action! source code as string
        origin: Code origin address (default $8000)

    Returns:
        SK-02 assembly code as string
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse_program()
    TypeChecker().check(ast)
    ConstantFolder().fold(ast)
    call_graph = CallGraph(ast)
    call_graph.check_no_recursion()
    codegen = CodeGenerator(call_graph, origin=origin)
    assembly = codegen.generate(ast)
    return assembly


def compile_file(
    input_file: str,
    output_file: str | None = None,
    *,
    origin: int = 0x8000,
) -> bool:
    """Compile Action! source file to SK-02 assembly file.

    Args:
        input_file: Path to .act input file
        output_file: Path to .asm output file (default: replace .act with .asm)
        origin: Code origin address (default $8000)

    Returns:
        True if compilation succeeded, False otherwise
    """
    try:
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_file}")
            return False

        source = input_path.read_text()
        assembly = compile_string(source, origin=origin)

        if output_file is None:
            output_file = str(input_path.with_suffix(".asm"))

        output_path = Path(output_file)
        output_path.write_text(assembly)

        print(f"Compiled {input_file} -> {output_file}")
        return True

    except Exception as e:
        print(f"Compilation error: {e}")
        return False
