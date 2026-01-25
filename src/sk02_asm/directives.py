"""Assembler directives (.ORG, .BYTE, .WORD, etc.)."""

from .errors import InvalidOperandError, SyntaxError
from .lexer import Token, TokenType


class Directive:
    """Base class for assembler directives."""

    @staticmethod
    def process_org(operands: list[Token]) -> int:
        """Process .ORG directive - returns new address."""
        if len(operands) != 1:
            raise SyntaxError(".ORG requires exactly one operand")

        token = operands[0]
        if token.type not in (TokenType.NUMBER, TokenType.CHAR):
            raise InvalidOperandError(".ORG requires a numeric address")

        address = int(token.value)
        if address < 0 or address > 0xFFFF:
            raise InvalidOperandError(f".ORG address out of range: ${address:04X}")

        return address

    @staticmethod
    def process_equ(operands: list[Token]) -> tuple[str, int]:
        """Process .EQU directive - returns (name, value)."""
        if len(operands) < 2:
            raise SyntaxError(".EQU requires name and value")

        name_token = operands[0]
        if name_token.type != TokenType.IDENTIFIER:
            raise InvalidOperandError(".EQU requires an identifier")

        # Skip comma if present
        value_idx = 1
        if operands[value_idx].type == TokenType.COMMA:
            value_idx += 1

        if value_idx >= len(operands):
            raise SyntaxError(".EQU requires a value")

        value_token = operands[value_idx]
        if value_token.type not in (TokenType.NUMBER, TokenType.CHAR):
            raise InvalidOperandError(".EQU requires a numeric value")

        return name_token.value, int(value_token.value)

    @staticmethod
    def process_byte(operands: list[Token]) -> list[int]:
        """Process .BYTE directive - returns list of bytes."""
        if not operands:
            raise SyntaxError(".BYTE requires at least one operand")

        bytes_out = []
        for token in operands:
            if token.type == TokenType.COMMA:
                continue
            if token.type not in (TokenType.NUMBER, TokenType.CHAR):
                raise InvalidOperandError(
                    f".BYTE requires numeric values, got {token.value}"
                )

            value = int(token.value)
            if value < 0 or value > 255:
                raise InvalidOperandError(f".BYTE value out of range: {value}")

            bytes_out.append(value)

        return bytes_out

    @staticmethod
    def process_word(operands: list[Token], symbols=None) -> list[int]:
        """
        Process .WORD directive - returns list of bytes (little-endian).
        Each word produces 2 bytes.
        """
        if not operands:
            raise SyntaxError(".WORD requires at least one operand")

        bytes_out = []
        for token in operands:
            if token.type == TokenType.COMMA:
                continue

            if token.type == TokenType.IDENTIFIER:
                # Label reference - will be resolved later
                if symbols and token.value in symbols.symbols:
                    value = symbols.lookup(token.value)
                else:
                    # Placeholder for second pass
                    value = 0
            elif token.type in (TokenType.NUMBER, TokenType.CHAR):
                value = int(token.value)
            else:
                raise InvalidOperandError(
                    f".WORD requires numeric values or labels, got {token.value}"
                )

            if value < 0 or value > 0xFFFF:
                raise InvalidOperandError(f".WORD value out of range: ${value:04X}")

            # Little-endian: low byte first, then high byte
            bytes_out.append(value & 0xFF)
            bytes_out.append((value >> 8) & 0xFF)

        return bytes_out

    @staticmethod
    def process_ascii(operands: list[Token]) -> list[int]:
        """Process .ASCII directive - returns ASCII bytes."""
        if not operands:
            raise SyntaxError(".ASCII requires a string")

        if operands[0].type != TokenType.STRING:
            raise InvalidOperandError(".ASCII requires a string literal")

        string = operands[0].value
        return [ord(c) for c in string]

    @staticmethod
    def process_asciiz(operands: list[Token]) -> list[int]:
        """Process .ASCIIZ directive - returns ASCII bytes with null terminator."""
        bytes_out = Directive.process_ascii(operands)
        bytes_out.append(0)  # Null terminator
        return bytes_out

    @staticmethod
    def get_size(directive: str, operands: list[Token], symbols=None) -> int:
        """Calculate the size in bytes of a directive."""
        directive = directive.upper()

        if directive == ".ORG":
            return 0  # Doesn't generate bytes
        elif directive == ".EQU":
            return 0  # Doesn't generate bytes
        elif directive == ".BYTE":
            return len(Directive.process_byte(operands))
        elif directive == ".WORD":
            # Count non-comma tokens * 2
            count = sum(1 for t in operands if t.type != TokenType.COMMA)
            return count * 2
        elif directive == ".ASCII":
            if operands and operands[0].type == TokenType.STRING:
                return len(operands[0].value)
            return 0
        elif directive == ".ASCIIZ":
            if operands and operands[0].type == TokenType.STRING:
                return len(operands[0].value) + 1  # +1 for null terminator
            return 0
        else:
            raise SyntaxError(f"Unknown directive: {directive}")
