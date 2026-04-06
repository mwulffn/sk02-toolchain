"""Token definitions for the SK-02 Action! lexer."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token types for Action! language."""

    # Literals
    NUMBER = auto()
    HEX_NUMBER = auto()
    CHAR_CONST = auto()
    STRING = auto()
    IDENTIFIER = auto()

    # Type keywords
    BYTE = auto()
    CHAR = auto()
    CARD = auto()
    INT = auto()

    # Extended type keywords
    POINTER = auto()
    ARRAY = auto()
    TYPE = auto()

    # Routine keywords
    PROC = auto()
    FUNC = auto()
    RETURN = auto()
    INTERRUPT = auto()

    # Control flow keywords
    IF = auto()
    THEN = auto()
    ELSEIF = auto()
    ELSE = auto()
    FI = auto()
    WHILE = auto()
    UNTIL = auto()
    FOR = auto()
    TO = auto()
    STEP = auto()
    DO = auto()
    OD = auto()
    EXIT = auto()

    # Keyword operators
    AND = auto()
    OR = auto()
    XOR = auto()
    MOD = auto()
    LSH = auto()
    RSH = auto()

    # Directive keywords
    MODULE = auto()
    DEFINE = auto()
    SET = auto()
    INCLUDE = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQ = auto()  # = (assignment and equality)
    NE = auto()  # <>
    LT = auto()  # <
    GT = auto()  # >
    LE = auto()  # <=
    GE = auto()  # >=
    AT = auto()  # @ (address-of)
    CARET = auto()  # ^ (dereference)
    PERCENT = auto()  # % (bitwise NOT)
    DOT = auto()  # . (record field access)

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()

    # Special
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "byte": TokenType.BYTE,
    "char": TokenType.CHAR,
    "card": TokenType.CARD,
    "int": TokenType.INT,
    "pointer": TokenType.POINTER,
    "array": TokenType.ARRAY,
    "type": TokenType.TYPE,
    "proc": TokenType.PROC,
    "func": TokenType.FUNC,
    "return": TokenType.RETURN,
    "interrupt": TokenType.INTERRUPT,
    "if": TokenType.IF,
    "then": TokenType.THEN,
    "elseif": TokenType.ELSEIF,
    "else": TokenType.ELSE,
    "fi": TokenType.FI,
    "while": TokenType.WHILE,
    "until": TokenType.UNTIL,
    "for": TokenType.FOR,
    "to": TokenType.TO,
    "step": TokenType.STEP,
    "do": TokenType.DO,
    "od": TokenType.OD,
    "exit": TokenType.EXIT,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "xor": TokenType.XOR,
    "mod": TokenType.MOD,
    "lsh": TokenType.LSH,
    "rsh": TokenType.RSH,
    "module": TokenType.MODULE,
    "define": TokenType.DEFINE,
    "set": TokenType.SET,
    "include": TokenType.INCLUDE,
}


@dataclass
class Token:
    """Represents a token in the source code."""

    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.column})"
