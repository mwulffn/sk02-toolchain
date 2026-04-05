"""Parser for assembly source lines."""

from dataclasses import dataclass

from .lexer import Lexer, Token, TokenType


@dataclass
class SourceLine:
    """Parsed source line."""

    line_num: int
    label: str | None = None
    directive: str | None = None
    mnemonic: str | None = None
    operands: list[Token] = None
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


def parse_source(source: str) -> list[SourceLine]:
    """Convenience function to parse source."""
    parser = Parser(source)
    return parser.parse()
