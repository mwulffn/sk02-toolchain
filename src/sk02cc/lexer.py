"""Lexer for SK02-C compiler."""

from .tokens import KEYWORDS, Token, TokenType

# Operator table: longest match first to ensure greedy tokenization.
# Each entry is (literal, TokenType).
_OPERATORS: list[tuple[str, TokenType]] = [
    ("<<=", TokenType.LSHIFT_ASSIGN),
    (">>=", TokenType.RSHIFT_ASSIGN),
    ("++", TokenType.INC),
    ("--", TokenType.DEC),
    ("==", TokenType.EQ),
    ("!=", TokenType.NE),
    ("<=", TokenType.LE),
    (">=", TokenType.GE),
    ("<<", TokenType.LSHIFT),
    (">>", TokenType.RSHIFT),
    ("&&", TokenType.LAND),
    ("||", TokenType.LOR),
    ("+=", TokenType.PLUS_ASSIGN),
    ("-=", TokenType.MINUS_ASSIGN),
    ("*=", TokenType.STAR_ASSIGN),
    ("/=", TokenType.SLASH_ASSIGN),
    ("%=", TokenType.PERCENT_ASSIGN),
    ("&=", TokenType.AND_ASSIGN),
    ("|=", TokenType.OR_ASSIGN),
    ("^=", TokenType.XOR_ASSIGN),
    ("+", TokenType.PLUS),
    ("-", TokenType.MINUS),
    ("*", TokenType.STAR),
    ("/", TokenType.SLASH),
    ("%", TokenType.PERCENT),
    ("&", TokenType.AMPERSAND),
    ("|", TokenType.PIPE),
    ("^", TokenType.CARET),
    ("~", TokenType.TILDE),
    ("!", TokenType.LNOT),
    ("=", TokenType.ASSIGN),
    ("<", TokenType.LT),
    (">", TokenType.GT),
    ("(", TokenType.LPAREN),
    (")", TokenType.RPAREN),
    ("{", TokenType.LBRACE),
    ("}", TokenType.RBRACE),
    ("[", TokenType.LBRACKET),
    ("]", TokenType.RBRACKET),
    (";", TokenType.SEMICOLON),
    (",", TokenType.COMMA),
]


class LexerError(Exception):
    """Lexer error exception."""

    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Lexer error at {line}:{column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """Tokenizes C source code."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def current_char(self) -> str | None:
        """Get current character or None if at end."""
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]

    def peek_char(self, offset: int = 1) -> str | None:
        """Peek ahead at character."""
        pos = self.pos + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]

    def advance(self) -> None:
        """Move to next character."""
        if self.pos < len(self.source):
            if self.source[self.pos] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.current_char() and self.current_char() in " \t\n\r":
            self.advance()

    def skip_line_comment(self) -> None:
        """Skip // style comment."""
        while self.current_char() and self.current_char() != "\n":
            self.advance()

    def skip_block_comment(self) -> None:
        """Skip /* */ style comment."""
        self.advance()  # skip *
        while self.current_char():
            if self.current_char() == "*" and self.peek_char() == "/":
                self.advance()  # skip *
                self.advance()  # skip /
                return
            self.advance()
        raise LexerError("Unterminated block comment", self.line, self.column)

    def read_number(self) -> Token:
        """Read numeric literal."""
        start_line = self.line
        start_col = self.column
        start_pos = self.pos

        # Handle hex numbers (0x...)
        if self.current_char() == "0" and self.peek_char() in "xX":
            self.advance()  # skip 0
            self.advance()  # skip x/X
            while (
                self.current_char() and self.current_char() in "0123456789abcdefABCDEF"
            ):
                self.advance()
        else:
            while self.current_char() and self.current_char().isdigit():
                self.advance()

        return Token(
            TokenType.NUMBER, self.source[start_pos : self.pos], start_line, start_col
        )

    def read_char_literal(self) -> Token:
        """Read character literal like 'A'."""
        start_line = self.line
        start_col = self.column
        self.advance()  # skip opening '

        if not self.current_char():
            raise LexerError("Unterminated character literal", start_line, start_col)

        char_value = ""
        if self.current_char() == "\\":
            # Escape sequence
            self.advance()
            if self.current_char() in "nrt0\\'\"":
                char_value = "\\" + self.current_char()
                self.advance()
            else:
                raise LexerError("Invalid escape sequence", self.line, self.column)
        else:
            char_value = self.current_char()
            self.advance()

        if self.current_char() != "'":
            raise LexerError("Unterminated character literal", self.line, self.column)
        self.advance()  # skip closing '

        return Token(TokenType.CHAR_LITERAL, char_value, start_line, start_col)

    def read_string_literal(self) -> Token:
        """Read string literal like \"hello\"."""
        start_line = self.line
        start_col = self.column
        self.advance()  # skip opening "

        string_value = ""
        while self.current_char() and self.current_char() != '"':
            if self.current_char() == "\\":
                self.advance()
                if self.current_char() in 'nrt0\\"':
                    string_value += "\\" + self.current_char()
                    self.advance()
                else:
                    raise LexerError("Invalid escape sequence", self.line, self.column)
            else:
                string_value += self.current_char()
                self.advance()

        if not self.current_char():
            raise LexerError("Unterminated string literal", start_line, start_col)

        self.advance()  # skip closing "
        return Token(TokenType.STRING_LITERAL, string_value, start_line, start_col)

    def read_identifier(self) -> Token:
        """Read identifier or keyword."""
        start_line = self.line
        start_col = self.column
        start_pos = self.pos

        while self.current_char() and (
            self.current_char().isalnum() or self.current_char() == "_"
        ):
            self.advance()

        ident = self.source[start_pos : self.pos]
        token_type = KEYWORDS.get(ident, TokenType.IDENTIFIER)
        return Token(token_type, ident, start_line, start_col)

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source code."""
        self.tokens = []

        while self.current_char():
            self.skip_whitespace()

            if not self.current_char():
                break

            start_line = self.line
            start_col = self.column
            ch = self.current_char()

            # Comments
            if ch == "/" and self.peek_char() == "/":
                self.advance()
                self.skip_line_comment()
                continue
            elif ch == "/" and self.peek_char() == "*":
                self.advance()
                self.skip_block_comment()
                continue

            # Numbers
            elif ch.isdigit():
                self.tokens.append(self.read_number())

            # Character literals
            elif ch == "'":
                self.tokens.append(self.read_char_literal())

            # String literals
            elif ch == '"':
                self.tokens.append(self.read_string_literal())

            # Identifiers and keywords
            elif ch.isalpha() or ch == "_":
                self.tokens.append(self.read_identifier())

            # Operators: try longest match first via the table.
            else:
                matched = False
                for op_str, op_type in _OPERATORS:
                    end = self.pos + len(op_str)
                    if self.source[self.pos : end] == op_str:
                        self.tokens.append(
                            Token(op_type, op_str, start_line, start_col)
                        )
                        for _ in op_str:
                            self.advance()
                        matched = True
                        break
                if not matched:
                    raise LexerError(
                        f"Unexpected character: {ch!r}", start_line, start_col
                    )

        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
