"""Lexer for tokenizing assembly source code."""

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token types."""

    LABEL = auto()
    MNEMONIC = auto()
    DIRECTIVE = auto()
    NUMBER = auto()
    STRING = auto()
    CHAR = auto()
    IDENTIFIER = auto()
    IMMEDIATE = auto()  # #value
    COMMA = auto()
    COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    """A token from the source."""

    type: TokenType
    value: str
    line: int
    column: int


class Lexer:
    """Tokenize assembly source code."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.split("\n")
        self.tokens: list[Token] = []
        self._tokenize()

    def _tokenize(self):
        """Tokenize the entire source."""
        for line_num, line in enumerate(self.lines, start=1):
            self._tokenize_line(line, line_num)

    def _tokenize_line(self, line: str, line_num: int):
        """Tokenize a single line."""
        # Remove comments
        comment_pos = line.find(";")
        if comment_pos != -1:
            comment = line[comment_pos:]
            line = line[:comment_pos]
            if comment.strip():
                self.tokens.append(
                    Token(TokenType.COMMENT, comment, line_num, comment_pos)
                )

        # Strip whitespace
        line = line.strip()
        if not line:
            return

        pos = 0

        # Check for label at start of line (global or local)
        if line and (line[0].isalpha() or line[0] == "." or line[0] == "_"):
            match = re.match(
                r"^(\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*):", line
            )
            if match:
                label = match.group(1)
                self.tokens.append(Token(TokenType.LABEL, label, line_num, 0))
                pos = match.end()
                line = line[pos:].strip()
                pos = 0

        # Check for directive
        has_directive = False
        if line.startswith("."):
            match = re.match(r"^(\.[A-Z]+)", line, re.IGNORECASE)
            if match:
                directive = match.group(1).upper()
                self.tokens.append(Token(TokenType.DIRECTIVE, directive, line_num, pos))
                has_directive = True
                pos = match.end()
                line = line[pos:].strip()
                pos = 0

        # Check for mnemonic (only if no directive on this line)
        if line and not has_directive:
            match = re.match(r"^([A-Z0-9_][A-Z0-9_>+\-<]*)", line, re.IGNORECASE)
            if match:
                mnemonic = match.group(1).upper()
                self.tokens.append(Token(TokenType.MNEMONIC, mnemonic, line_num, pos))
                pos = match.end()
                line = line[pos:].strip()
                pos = 0

        # Process operands
        while line:
            # Skip whitespace
            match = re.match(r"^\s+", line)
            if match:
                pos += match.end()
                line = line[match.end() :]
                continue

            # Immediate value (#)
            if line.startswith("#"):
                self.tokens.append(Token(TokenType.IMMEDIATE, "#", line_num, pos))
                pos += 1
                line = line[1:]
                continue

            # Hex number ($XXXX)
            match = re.match(r"^\$([0-9A-Fa-f]+)", line)
            if match:
                value = int(match.group(1), 16)
                self.tokens.append(Token(TokenType.NUMBER, str(value), line_num, pos))
                pos += match.end()
                line = line[match.end() :]
                continue

            # Binary number (%XXXXXXXX)
            match = re.match(r"^%([01]+)", line)
            if match:
                value = int(match.group(1), 2)
                self.tokens.append(Token(TokenType.NUMBER, str(value), line_num, pos))
                pos += match.end()
                line = line[match.end() :]
                continue

            # Character literal ('X')
            match = re.match(r"^'(.)'", line)
            if match:
                char = match.group(1)
                value = ord(char)
                self.tokens.append(Token(TokenType.CHAR, str(value), line_num, pos))
                pos += match.end()
                line = line[match.end() :]
                continue

            # Decimal number
            match = re.match(r"^(\d+)", line)
            if match:
                self.tokens.append(
                    Token(TokenType.NUMBER, match.group(1), line_num, pos)
                )
                pos += match.end()
                line = line[match.end() :]
                continue

            # String literal
            if line.startswith('"'):
                match = re.match(r'^"([^"]*)"', line)
                if match:
                    self.tokens.append(
                        Token(TokenType.STRING, match.group(1), line_num, pos)
                    )
                    pos += match.end()
                    line = line[match.end() :]
                    continue

            # Comma
            if line.startswith(","):
                self.tokens.append(Token(TokenType.COMMA, ",", line_num, pos))
                pos += 1
                line = line[1:].strip()
                continue

            # Identifier (label reference)
            match = re.match(
                r"^(\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*)", line
            )
            if match:
                self.tokens.append(
                    Token(TokenType.IDENTIFIER, match.group(1), line_num, pos)
                )
                pos += match.end()
                line = line[match.end() :]
                continue

            # Unknown character
            break

    def get_tokens(self) -> list[Token]:
        """Return all tokens."""
        return self.tokens
