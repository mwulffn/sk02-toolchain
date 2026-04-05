"""Lexer for SK02-C compiler."""

from .tokens import KEYWORDS, Token, TokenType


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
        num_str = ""

        # Handle hex numbers (0x...)
        if self.current_char() == "0" and self.peek_char() in "xX":
            num_str += self.current_char()
            self.advance()
            num_str += self.current_char()
            self.advance()
            while (
                self.current_char() and self.current_char() in "0123456789abcdefABCDEF"
            ):
                num_str += self.current_char()
                self.advance()
        else:
            # Decimal number
            while self.current_char() and self.current_char().isdigit():
                num_str += self.current_char()
                self.advance()

        return Token(TokenType.NUMBER, num_str, start_line, start_col)

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
                raise LexerError(f"Invalid escape sequence", self.line, self.column)
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
        ident = ""

        while self.current_char() and (
            self.current_char().isalnum() or self.current_char() == "_"
        ):
            ident += self.current_char()
            self.advance()

        # Check if it's a keyword
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

            # Two-character operators
            elif ch == "+" and self.peek_char() == "+":
                self.tokens.append(Token(TokenType.INC, "++", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "-" and self.peek_char() == "-":
                self.tokens.append(Token(TokenType.DEC, "--", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "=" and self.peek_char() == "=":
                self.tokens.append(Token(TokenType.EQ, "==", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "!" and self.peek_char() == "=":
                self.tokens.append(Token(TokenType.NE, "!=", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "<" and self.peek_char() == "=":
                self.tokens.append(Token(TokenType.LE, "<=", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == ">" and self.peek_char() == "=":
                self.tokens.append(Token(TokenType.GE, ">=", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "<" and self.peek_char() == "<":
                self.tokens.append(Token(TokenType.LSHIFT, "<<", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == ">" and self.peek_char() == ">":
                self.tokens.append(Token(TokenType.RSHIFT, ">>", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "&" and self.peek_char() == "&":
                self.tokens.append(Token(TokenType.LAND, "&&", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "|" and self.peek_char() == "|":
                self.tokens.append(Token(TokenType.LOR, "||", start_line, start_col))
                self.advance()
                self.advance()
            elif ch == "+" and self.peek_char() == "=":
                self.tokens.append(
                    Token(TokenType.PLUS_ASSIGN, "+=", start_line, start_col)
                )
                self.advance()
                self.advance()
            elif ch == "-" and self.peek_char() == "=":
                self.tokens.append(
                    Token(TokenType.MINUS_ASSIGN, "-=", start_line, start_col)
                )
                self.advance()
                self.advance()
            elif ch == "&" and self.peek_char() == "=":
                self.tokens.append(
                    Token(TokenType.AND_ASSIGN, "&=", start_line, start_col)
                )
                self.advance()
                self.advance()
            elif ch == "|" and self.peek_char() == "=":
                self.tokens.append(
                    Token(TokenType.OR_ASSIGN, "|=", start_line, start_col)
                )
                self.advance()
                self.advance()
            elif ch == "^" and self.peek_char() == "=":
                self.tokens.append(
                    Token(TokenType.XOR_ASSIGN, "^=", start_line, start_col)
                )
                self.advance()
                self.advance()

            # Single-character tokens
            elif ch == "+":
                self.tokens.append(Token(TokenType.PLUS, "+", start_line, start_col))
                self.advance()
            elif ch == "-":
                self.tokens.append(Token(TokenType.MINUS, "-", start_line, start_col))
                self.advance()
            elif ch == "*":
                self.advance()
                if self.pos < len(self.source) and self.source[self.pos] == "=":
                    self.tokens.append(
                        Token(TokenType.STAR_ASSIGN, "*=", start_line, start_col)
                    )
                    self.advance()
                else:
                    self.tokens.append(
                        Token(TokenType.STAR, "*", start_line, start_col)
                    )
            elif ch == "/":
                self.advance()
                if self.pos < len(self.source) and self.source[self.pos] == "=":
                    self.tokens.append(
                        Token(TokenType.SLASH_ASSIGN, "/=", start_line, start_col)
                    )
                    self.advance()
                else:
                    self.tokens.append(
                        Token(TokenType.SLASH, "/", start_line, start_col)
                    )
            elif ch == "%":
                self.advance()
                if self.pos < len(self.source) and self.source[self.pos] == "=":
                    self.tokens.append(
                        Token(TokenType.PERCENT_ASSIGN, "%=", start_line, start_col)
                    )
                    self.advance()
                else:
                    self.tokens.append(
                        Token(TokenType.PERCENT, "%", start_line, start_col)
                    )
            elif ch == "&":
                self.tokens.append(
                    Token(TokenType.AMPERSAND, "&", start_line, start_col)
                )
                self.advance()
            elif ch == "|":
                self.tokens.append(Token(TokenType.PIPE, "|", start_line, start_col))
                self.advance()
            elif ch == "^":
                self.tokens.append(Token(TokenType.CARET, "^", start_line, start_col))
                self.advance()
            elif ch == "~":
                self.tokens.append(Token(TokenType.TILDE, "~", start_line, start_col))
                self.advance()
            elif ch == "!":
                self.tokens.append(Token(TokenType.LNOT, "!", start_line, start_col))
                self.advance()
            elif ch == "=":
                self.tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col))
                self.advance()
            elif ch == "<":
                self.tokens.append(Token(TokenType.LT, "<", start_line, start_col))
                self.advance()
            elif ch == ">":
                self.tokens.append(Token(TokenType.GT, ">", start_line, start_col))
                self.advance()
            elif ch == "(":
                self.tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col))
                self.advance()
            elif ch == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col))
                self.advance()
            elif ch == "{":
                self.tokens.append(Token(TokenType.LBRACE, "{", start_line, start_col))
                self.advance()
            elif ch == "}":
                self.tokens.append(Token(TokenType.RBRACE, "}", start_line, start_col))
                self.advance()
            elif ch == "[":
                self.tokens.append(
                    Token(TokenType.LBRACKET, "[", start_line, start_col)
                )
                self.advance()
            elif ch == "]":
                self.tokens.append(
                    Token(TokenType.RBRACKET, "]", start_line, start_col)
                )
                self.advance()
            elif ch == ";":
                self.tokens.append(
                    Token(TokenType.SEMICOLON, ";", start_line, start_col)
                )
                self.advance()
            elif ch == ",":
                self.tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))
                self.advance()

            else:
                raise LexerError(f"Unexpected character: {ch!r}", start_line, start_col)

        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
