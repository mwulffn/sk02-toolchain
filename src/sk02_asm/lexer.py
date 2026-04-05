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
        """Tokenize a single line.

        ``col`` always tracks the column offset into the *original* ``line``
        string so that all emitted Token.column values are accurate.
        """
        original = line  # keep for column calculations

        # Remove comments (preserving original column reference)
        comment_pos = line.find(";")
        if comment_pos != -1:
            comment = line[comment_pos:]
            line = line[:comment_pos]
            if comment.strip():
                self.tokens.append(
                    Token(TokenType.COMMENT, comment, line_num, comment_pos)
                )

        # Find first non-whitespace column so all positions are in original coords.
        stripped = line.strip()
        if not stripped:
            return

        # col = current scan position within `original` (not the stripped copy).
        # We work on `remaining` which is a suffix of `original` starting at col.
        col = len(original) - len(original.lstrip())
        remaining = original[col:comment_pos if comment_pos != -1 else len(original)].rstrip()

        # Check for label at start of line (global or local)
        match = re.match(
            r"^(\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*):", remaining
        )
        if match:
            self.tokens.append(Token(TokenType.LABEL, match.group(1), line_num, col))
            col += match.end()
            remaining = remaining[match.end():]
            ws = len(remaining) - len(remaining.lstrip())
            col += ws
            remaining = remaining[ws:]

        # Check for directive
        has_directive = False
        match = re.match(r"^(\.[A-Z]+)", remaining, re.IGNORECASE)
        if match:
            self.tokens.append(Token(TokenType.DIRECTIVE, match.group(1).upper(), line_num, col))
            has_directive = True
            col += match.end()
            after = remaining[match.end():]
            col += len(after) - len(after.lstrip())
            remaining = after.lstrip()

        # Check for mnemonic (only if no directive on this line)
        if remaining and not has_directive:
            match = re.match(r"^([A-Z0-9_][A-Z0-9_>+\-<]*)", remaining, re.IGNORECASE)
            if match:
                self.tokens.append(Token(TokenType.MNEMONIC, match.group(1).upper(), line_num, col))
                col += match.end()
                after = remaining[match.end():]
                col += len(after) - len(after.lstrip())
                remaining = after.lstrip()

        # Process operands
        while remaining:
            # Skip leading whitespace (already stripped above; handle mid-operand spaces)
            ws = re.match(r"^\s+", remaining)
            if ws:
                col += ws.end()
                remaining = remaining[ws.end():]
                continue

            # Immediate value (#)
            if remaining.startswith("#"):
                self.tokens.append(Token(TokenType.IMMEDIATE, "#", line_num, col))
                col += 1
                remaining = remaining[1:]
                continue

            # Hex number ($XXXX)
            match = re.match(r"^\$([0-9A-Fa-f]+)", remaining)
            if match:
                value = int(match.group(1), 16)
                self.tokens.append(Token(TokenType.NUMBER, str(value), line_num, col))
                col += match.end()
                remaining = remaining[match.end():]
                continue

            # Binary number (%XXXXXXXX)
            match = re.match(r"^%([01]+)", remaining)
            if match:
                value = int(match.group(1), 2)
                self.tokens.append(Token(TokenType.NUMBER, str(value), line_num, col))
                col += match.end()
                remaining = remaining[match.end():]
                continue

            # Character literal ('X')
            match = re.match(r"^'(.)'", remaining)
            if match:
                self.tokens.append(Token(TokenType.CHAR, str(ord(match.group(1))), line_num, col))
                col += match.end()
                remaining = remaining[match.end():]
                continue

            # Decimal number
            match = re.match(r"^(\d+)", remaining)
            if match:
                self.tokens.append(Token(TokenType.NUMBER, match.group(1), line_num, col))
                col += match.end()
                remaining = remaining[match.end():]
                continue

            # String literal
            if remaining.startswith('"'):
                match = re.match(r'^"([^"]*)"', remaining)
                if match:
                    self.tokens.append(Token(TokenType.STRING, match.group(1), line_num, col))
                    col += match.end()
                    remaining = remaining[match.end():]
                    continue

            # Comma
            if remaining.startswith(","):
                self.tokens.append(Token(TokenType.COMMA, ",", line_num, col))
                col += 1
                remaining = remaining[1:].lstrip()
                continue

            # Identifier (label reference)
            match = re.match(
                r"^(\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*)", remaining
            )
            if match:
                self.tokens.append(Token(TokenType.IDENTIFIER, match.group(1), line_num, col))
                col += match.end()
                remaining = remaining[match.end():]
                continue

            # Unknown character — stop silently (existing behaviour)
            break

    def get_tokens(self) -> list[Token]:
        """Return all tokens."""
        return self.tokens
