"""Parser for assembly source lines."""

from dataclasses import dataclass
from typing import Any

from .errors import SyntaxError
from .lexer import Lexer, Token, TokenType


@dataclass
class SourceLine:
    """Parsed source line."""

    line_num: int
    label: str | None = None
    directive: str | None = None
    mnemonic: str | None = None
    operands: list[Any] = None
    comment: str | None = None
    original: str = ""

    def __post_init__(self):
        if self.operands is None:
            self.operands = []


class Parser:
    """Parse assembly source into structured lines."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.split("\n")
        self.lexer = Lexer(source)
        self.tokens = self.lexer.get_tokens()
        self.pos = 0
        self.parsed_lines: list[SourceLine] = []

    def parse(self) -> list[SourceLine]:
        """Parse all source lines."""
        current_line_num = 0
        current_line = SourceLine(line_num=0)

        for token in self.tokens:
            if token.line != current_line_num:
                # Save previous line if it has content
                if current_line_num > 0:
                    current_line.original = self.lines[current_line_num - 1]
                    self.parsed_lines.append(current_line)

                # Start new line
                current_line_num = token.line
                current_line = SourceLine(line_num=current_line_num)

            if token.type == TokenType.LABEL:
                current_line.label = token.value
            elif token.type == TokenType.DIRECTIVE:
                current_line.directive = token.value
            elif token.type == TokenType.MNEMONIC:
                current_line.mnemonic = token.value
            elif token.type == TokenType.COMMENT:
                current_line.comment = token.value
            elif token.type == TokenType.IMMEDIATE:
                # Next token should be the value
                continue
            elif token.type in (
                TokenType.NUMBER,
                TokenType.CHAR,
                TokenType.STRING,
                TokenType.IDENTIFIER,
            ):
                current_line.operands.append(token)
            elif token.type == TokenType.COMMA:
                # Separator for multiple operands
                continue

        # Save last line
        if current_line_num > 0:
            current_line.original = self.lines[current_line_num - 1]
            self.parsed_lines.append(current_line)

        return self.parsed_lines

    def parse_operand(self, tokens: list[Token]) -> tuple[int, bool]:
        """
        Parse operand tokens into a value and immediate flag.
        Returns (value, is_immediate).
        """
        if not tokens:
            raise SyntaxError("Missing operand")

        is_immediate = False
        token_idx = 0

        # Check for immediate prefix
        if tokens[0].type == TokenType.IMMEDIATE:
            is_immediate = True
            token_idx = 1
            if len(tokens) <= token_idx:
                raise SyntaxError("Missing value after #")

        token = tokens[token_idx]

        if token.type in (TokenType.NUMBER, TokenType.CHAR):
            return int(token.value), is_immediate
        elif token.type == TokenType.IDENTIFIER:
            # Will be resolved in second pass
            return token.value, is_immediate
        else:
            raise SyntaxError(f"Invalid operand: {token.value}")


def parse_source(source: str) -> list[SourceLine]:
    """Convenience function to parse source."""
    parser = Parser(source)
    return parser.parse()
