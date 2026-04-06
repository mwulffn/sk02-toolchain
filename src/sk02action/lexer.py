"""Lexer for the SK-02 Action! compiler."""

from .tokens import KEYWORDS, Token, TokenType


class LexerError(Exception):
    """Lexer error with source position."""

    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Lexer error at {line}:{column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """Character-by-character tokenizer for Action! source code.

    Case-insensitive: all identifiers and keywords are normalized to lowercase.
    Comments start with `;` and extend to end of line.
    """

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1

    def _peek(self) -> str:
        if self.pos >= len(self.source):
            return ""
        return self.source[self.pos]

    def _peek_ahead(self, offset: int = 1) -> str:
        pos = self.pos + offset
        if pos >= len(self.source):
            return ""
        return self.source[pos]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _at_end(self) -> bool:
        return self.pos >= len(self.source)

    def _skip_whitespace_and_comments(self) -> None:
        while not self._at_end():
            ch = self._peek()
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            elif ch == ";":
                # Comment: skip to end of line
                while not self._at_end() and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _read_identifier(self) -> Token:
        start_line = self.line
        start_col = self.column
        chars = []
        while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
            chars.append(self._advance())
        value = "".join(chars).lower()
        token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, start_line, start_col)

    def _read_number(self) -> Token:
        start_line = self.line
        start_col = self.column
        chars = []
        while not self._at_end() and self._peek().isdigit():
            chars.append(self._advance())
        return Token(TokenType.NUMBER, "".join(chars), start_line, start_col)

    def _read_hex_number(self) -> Token:
        start_line = self.line
        start_col = self.column
        chars = [self._advance()]  # consume '$'
        if self._at_end() or not self._is_hex_digit(self._peek()):
            raise LexerError("Expected hex digit after '$'", start_line, start_col)
        while not self._at_end() and self._is_hex_digit(self._peek()):
            chars.append(self._advance())
        return Token(TokenType.HEX_NUMBER, "".join(chars), start_line, start_col)

    def _read_char_const(self) -> Token:
        start_line = self.line
        start_col = self.column
        chars = [self._advance()]  # consume "'"
        if self._at_end():
            raise LexerError('Expected character after "\'"', start_line, start_col)
        chars.append(self._advance())  # consume the character
        return Token(TokenType.CHAR_CONST, "".join(chars), start_line, start_col)

    def _read_string(self) -> Token:
        start_line = self.line
        start_col = self.column
        chars = [self._advance()]  # consume opening '"'
        while True:
            if self._at_end():
                raise LexerError("Unterminated string", start_line, start_col)
            ch = self._advance()
            chars.append(ch)
            if ch == '"':
                # Check for escaped quote ""
                if not self._at_end() and self._peek() == '"':
                    chars.append(self._advance())
                else:
                    break
        return Token(TokenType.STRING, "".join(chars), start_line, start_col)

    @staticmethod
    def _is_hex_digit(ch: str) -> bool:
        return ch in "0123456789abcdefABCDEF"

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return a list of tokens."""
        tokens: list[Token] = []

        while True:
            self._skip_whitespace_and_comments()
            if self._at_end():
                tokens.append(Token(TokenType.EOF, "", self.line, self.column))
                break

            ch = self._peek()
            start_line = self.line
            start_col = self.column

            # Identifiers and keywords
            if ch.isalpha() or ch == "_":
                tokens.append(self._read_identifier())

            # Decimal numbers
            elif ch.isdigit():
                tokens.append(self._read_number())

            # Hex numbers
            elif ch == "$":
                tokens.append(self._read_hex_number())

            # Character constants
            elif ch == "'":
                tokens.append(self._read_char_const())

            # String constants
            elif ch == '"':
                tokens.append(self._read_string())

            # Two-character operators (must check before single-char)
            elif ch == "<":
                self._advance()
                if not self._at_end() and self._peek() == ">":
                    self._advance()
                    tokens.append(Token(TokenType.NE, "<>", start_line, start_col))
                elif not self._at_end() and self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.LE, "<=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.LT, "<", start_line, start_col))

            elif ch == ">":
                self._advance()
                if not self._at_end() and self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.GE, ">=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.GT, ">", start_line, start_col))

            # Single-character operators and delimiters
            elif ch == "+":
                self._advance()
                tokens.append(Token(TokenType.PLUS, "+", start_line, start_col))
            elif ch == "-":
                self._advance()
                tokens.append(Token(TokenType.MINUS, "-", start_line, start_col))
            elif ch == "*":
                self._advance()
                tokens.append(Token(TokenType.STAR, "*", start_line, start_col))
            elif ch == "/":
                self._advance()
                tokens.append(Token(TokenType.SLASH, "/", start_line, start_col))
            elif ch == "=":
                self._advance()
                tokens.append(Token(TokenType.EQ, "=", start_line, start_col))
            elif ch == "@":
                self._advance()
                tokens.append(Token(TokenType.AT, "@", start_line, start_col))
            elif ch == "^":
                self._advance()
                tokens.append(Token(TokenType.CARET, "^", start_line, start_col))
            elif ch == "%":
                self._advance()
                tokens.append(Token(TokenType.PERCENT, "%", start_line, start_col))
            elif ch == ".":
                self._advance()
                tokens.append(Token(TokenType.DOT, ".", start_line, start_col))
            elif ch == "(":
                self._advance()
                tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col))
            elif ch == ")":
                self._advance()
                tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col))
            elif ch == "[":
                self._advance()
                tokens.append(Token(TokenType.LBRACKET, "[", start_line, start_col))
            elif ch == "]":
                self._advance()
                tokens.append(Token(TokenType.RBRACKET, "]", start_line, start_col))
            elif ch == ",":
                self._advance()
                tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))

            else:
                raise LexerError(f"Unexpected character: {ch!r}", start_line, start_col)

        return tokens
