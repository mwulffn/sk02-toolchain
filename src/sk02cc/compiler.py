"""Main compiler module for SK02-C."""

from pathlib import Path

from .codegen import CodeGenerator
from .lexer import Lexer
from .parser import Parser


def compile_string(source: str) -> str:
    """Compile C source code to SK-02 assembly.

    Args:
        source: C source code as string

    Returns:
        SK-02 assembly code as string

    Raises:
        LexerError: If there's a tokenization error
        ParseError: If there's a syntax error
        CodeGenError: If code generation fails
    """
    # Tokenize
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    # Parse
    parser = Parser(tokens)
    ast = parser.parse_program()

    # Generate code
    codegen = CodeGenerator()
    assembly = codegen.generate(ast)

    return assembly


def compile_file(input_file: str, output_file: str | None = None) -> bool:
    """Compile C source file to SK-02 assembly file.

    Args:
        input_file: Path to .c input file
        output_file: Path to .asm output file (default: replace .c with .asm)

    Returns:
        True if compilation succeeded, False otherwise
    """
    try:
        # Read input
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_file}")
            return False

        source = input_path.read_text()

        # Compile
        assembly = compile_string(source)

        # Determine output file
        if output_file is None:
            output_file = str(input_path.with_suffix(".asm"))

        # Write output
        output_path = Path(output_file)
        output_path.write_text(assembly)

        print(f"Compiled {input_file} -> {output_file}")
        return True

    except Exception as e:
        print(f"Compilation error: {e}")
        return False
