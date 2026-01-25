"""Two-pass assembler for SK-02."""

from pathlib import Path

from .directives import Directive
from .errors import (
    AssemblyError,
    InvalidOpcodeError,
    InvalidOperandError,
)
from .lexer import TokenType
from .opcodes import OperandType, get_opcode
from .output import BinaryWriter, IntelHexWriter
from .parser import SourceLine, parse_source
from .symbols import SymbolTable


class Assembler:
    """Two-pass assembler."""

    def __init__(self, source: str, start_address: int = 0x8000):
        self.source = source
        self.start_address = start_address
        self.symbols = SymbolTable()
        self.lines: list[SourceLine] = []
        self.errors: list[AssemblyError] = []
        self.current_address = start_address

    def assemble(self) -> tuple[BinaryWriter, list[AssemblyError]]:
        """
        Assemble source code in two passes.
        Returns (binary_output, errors).
        """
        # Parse source
        try:
            self.lines = parse_source(self.source)
        except AssemblyError as e:
            self.errors.append(e)
            return BinaryWriter(self.start_address), self.errors

        # Pass 1: Build symbol table
        self._pass1()

        # Pass 2: Generate code
        if not self.errors:
            output = self._pass2()
        else:
            output = BinaryWriter(self.start_address)

        return output, self.errors

    def _pass1(self):
        """Pass 1: Build symbol table and calculate addresses."""
        self.current_address = self.start_address

        for line in self.lines:
            try:
                # Handle label
                if line.label:
                    self.symbols.define(line.label, self.current_address, line.line_num)
                    if not line.label.startswith("."):
                        self.symbols.set_global_scope(line.label)

                # Handle directive
                if line.directive:
                    self._process_directive_pass1(line)
                # Handle instruction
                elif line.mnemonic:
                    self._process_instruction_pass1(line)

            except AssemblyError as e:
                if e.line_num is None:
                    e.line_num = line.line_num
                if e.line is None:
                    e.line = line.original
                self.errors.append(e)

    def _pass2(self) -> BinaryWriter:
        """Pass 2: Generate machine code."""
        self.current_address = self.start_address
        output = BinaryWriter(self.start_address)

        for line in self.lines:
            try:
                # Update global scope for local label resolution
                if line.label and not line.label.startswith("."):
                    self.symbols.set_global_scope(line.label)

                # Handle directive
                if line.directive:
                    self._process_directive_pass2(line, output)
                # Handle instruction
                elif line.mnemonic:
                    self._process_instruction_pass2(line, output)

            except AssemblyError as e:
                if e.line_num is None:
                    e.line_num = line.line_num
                if e.line is None:
                    e.line = line.original
                self.errors.append(e)

        return output

    def _process_directive_pass1(self, line: SourceLine):
        """Process directive in pass 1 (update address)."""
        directive = line.directive.upper()

        if directive == ".ORG":
            self.current_address = Directive.process_org(line.operands)
        elif directive == ".EQU":
            name, value = Directive.process_equ(line.operands)
            self.symbols.define(name, value, line.line_num)
        else:
            # Other directives affect address
            size = Directive.get_size(directive, line.operands, self.symbols)
            self.current_address += size

    def _process_directive_pass2(self, line: SourceLine, output: BinaryWriter):
        """Process directive in pass 2 (generate bytes)."""
        directive = line.directive.upper()

        if directive == ".ORG":
            self.current_address = Directive.process_org(line.operands)
        elif directive == ".EQU":
            # Already processed in pass 1
            pass
        elif directive == ".BYTE":
            bytes_out = Directive.process_byte(line.operands)
            output.write_bytes(self.current_address, bytes_out)
            self.current_address += len(bytes_out)
        elif directive == ".WORD":
            bytes_out = Directive.process_word(line.operands, self.symbols)
            # Resolve any label references
            i = 0
            for token in line.operands:
                if token.type == TokenType.COMMA:
                    continue
                if token.type == TokenType.IDENTIFIER:
                    # Resolve label
                    value = self.symbols.lookup(token.value)
                    bytes_out[i] = value & 0xFF
                    bytes_out[i + 1] = (value >> 8) & 0xFF
                i += 2
            output.write_bytes(self.current_address, bytes_out)
            self.current_address += len(bytes_out)
        elif directive == ".ASCII":
            bytes_out = Directive.process_ascii(line.operands)
            output.write_bytes(self.current_address, bytes_out)
            self.current_address += len(bytes_out)
        elif directive == ".ASCIIZ":
            bytes_out = Directive.process_asciiz(line.operands)
            output.write_bytes(self.current_address, bytes_out)
            self.current_address += len(bytes_out)

    def _process_instruction_pass1(self, line: SourceLine):
        """Process instruction in pass 1 (calculate size)."""
        opcode = get_opcode(line.mnemonic)
        if opcode is None:
            raise InvalidOpcodeError(f"Unknown opcode: {line.mnemonic}", line.line_num)

        self.current_address += opcode.size

    def _process_instruction_pass2(self, line: SourceLine, output: BinaryWriter):
        """Process instruction in pass 2 (generate bytes)."""
        opcode = get_opcode(line.mnemonic)
        if opcode is None:
            raise InvalidOpcodeError(f"Unknown opcode: {line.mnemonic}", line.line_num)

        # Write opcode byte
        output.write_byte(self.current_address, opcode.value)
        addr = self.current_address + 1

        # Handle operands
        if opcode.operand == OperandType.NONE:
            # No operand
            if line.operands:
                raise InvalidOperandError(
                    f"{line.mnemonic} takes no operands", line.line_num
                )
        elif opcode.operand == OperandType.IMM8:
            # 8-bit immediate
            if not line.operands:
                raise InvalidOperandError(
                    f"{line.mnemonic} requires an 8-bit immediate value", line.line_num
                )
            value = self._resolve_operand(line.operands[0])
            if value < 0 or value > 255:
                raise InvalidOperandError(
                    f"8-bit immediate value out of range: {value}", line.line_num
                )
            output.write_byte(addr, value)
            addr += 1
        elif opcode.operand == OperandType.IMM16:
            # 16-bit immediate (little-endian)
            if not line.operands:
                raise InvalidOperandError(
                    f"{line.mnemonic} requires a 16-bit immediate value", line.line_num
                )
            value = self._resolve_operand(line.operands[0])
            if value < 0 or value > 0xFFFF:
                raise InvalidOperandError(
                    f"16-bit immediate value out of range: ${value:04X}", line.line_num
                )
            output.write_byte(addr, value & 0xFF)  # Low byte
            output.write_byte(addr + 1, (value >> 8) & 0xFF)  # High byte
            addr += 2
        elif opcode.operand == OperandType.ADDR16:
            # 16-bit address (little-endian)
            if not line.operands:
                raise InvalidOperandError(
                    f"{line.mnemonic} requires a 16-bit address", line.line_num
                )
            value = self._resolve_operand(line.operands[0])
            if value < 0 or value > 0xFFFF:
                raise InvalidOperandError(
                    f"Address out of range: ${value:04X}", line.line_num
                )
            output.write_byte(addr, value & 0xFF)  # Low byte
            output.write_byte(addr + 1, (value >> 8) & 0xFF)  # High byte
            addr += 2

        self.current_address = addr

    def _resolve_operand(self, token):
        """Resolve an operand token to a numeric value."""
        if token.type in (TokenType.NUMBER, TokenType.CHAR):
            return int(token.value)
        elif token.type == TokenType.IDENTIFIER:
            return self.symbols.lookup(token.value)
        else:
            raise InvalidOperandError(f"Invalid operand: {token.value}")


def assemble_file(
    input_file: str | Path,
    output_file: str | Path | None = None,
    format: str = "bin",
    start_address: int = 0x8000,
) -> bool:
    """
    Assemble a file.
    Returns True if successful, False if errors occurred.
    """
    input_path = Path(input_file)

    # Determine output filename
    if output_file is None:
        if format == "hex":
            output_path = input_path.with_suffix(".hex")
        else:
            output_path = input_path.with_suffix(".bin")
    else:
        output_path = Path(output_file)

    # Read source
    with open(input_path, "r") as f:
        source = f.read()

    # Assemble
    assembler = Assembler(source, start_address)
    output, errors = assembler.assemble()

    # Report errors
    if errors:
        for error in errors:
            print(f"Error: {error}")
        return False

    # Write output
    if format == "hex":
        hex_output = IntelHexWriter()
        for addr, byte in output.data.items():
            hex_output.write_byte(addr, byte)
        hex_output.save(output_path)
    else:
        output.save(output_path)

    print(f"Assembly successful: {output_path}")
    return True
