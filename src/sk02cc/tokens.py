"""Token definitions for SK02-C lexer."""

from enum import Enum, auto


class TokenType(Enum):
    """Token types for C subset."""

    # Literals
    NUMBER = auto()
    CHAR_LITERAL = auto()
    STRING_LITERAL = auto()
    IDENTIFIER = auto()

    # Keywords
    CHAR = auto()
    INT = auto()
    VOID = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    BREAK = auto()
    CONTINUE = auto()
    REGISTER = auto()
    STATIC = auto()
    CONST = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    AMPERSAND = auto()
    PIPE = auto()
    CARET = auto()
    TILDE = auto()
    LSHIFT = auto()
    RSHIFT = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    LAND = auto()
    LOR = auto()
    LNOT = auto()
    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()
    AND_ASSIGN = auto()
    OR_ASSIGN = auto()
    XOR_ASSIGN = auto()
    LSHIFT_ASSIGN = auto()
    RSHIFT_ASSIGN = auto()
    INC = auto()
    DEC = auto()

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMICOLON = auto()
    COMMA = auto()

    # Special
    EOF = auto()
    NEWLINE = auto()


KEYWORDS = {
    "char": TokenType.CHAR,
    "int": TokenType.INT,
    "void": TokenType.VOID,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "register": TokenType.REGISTER,
    "static": TokenType.STATIC,
    "const": TokenType.CONST,
}


class Token:
    """Represents a token in the source code."""

    def __init__(
        self, type: TokenType, value: str, line: int, column: int
    ):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.column})"

    def __str__(self) -> str:
        return self.value
