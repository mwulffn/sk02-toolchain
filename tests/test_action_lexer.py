"""Tests for the SK-02 Action! lexer.

Red/green: tests written first, then lexer implemented to pass them.
"""

import pytest

from sk02action.lexer import Lexer, LexerError
from sk02action.tokens import TokenType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def lex(source: str) -> list[tuple[TokenType, str]]:
    """Tokenize source and return list of (type, value) pairs, excluding EOF."""
    tokens = Lexer(source).tokenize()
    return [(t.type, t.value) for t in tokens if t.type != TokenType.EOF]


# ===========================================================================
# Keywords
# ===========================================================================


class TestTokenizeKeywords:
    """All Action! keywords tokenize correctly, case-insensitively."""

    def test_byte(self):
        assert lex("BYTE") == [(TokenType.BYTE, "byte")]

    def test_card(self):
        assert lex("CARD") == [(TokenType.CARD, "card")]

    def test_int(self):
        assert lex("INT") == [(TokenType.INT, "int")]

    def test_char(self):
        assert lex("CHAR") == [(TokenType.CHAR, "char")]

    def test_proc(self):
        assert lex("PROC") == [(TokenType.PROC, "proc")]

    def test_func(self):
        assert lex("FUNC") == [(TokenType.FUNC, "func")]

    def test_return(self):
        assert lex("RETURN") == [(TokenType.RETURN, "return")]

    def test_if_then_fi(self):
        result = lex("IF THEN FI")
        assert result == [
            (TokenType.IF, "if"),
            (TokenType.THEN, "then"),
            (TokenType.FI, "fi"),
        ]

    def test_elseif_else(self):
        result = lex("ELSEIF ELSE")
        assert result == [
            (TokenType.ELSEIF, "elseif"),
            (TokenType.ELSE, "else"),
        ]

    def test_while_do_od(self):
        result = lex("WHILE DO OD")
        assert result == [
            (TokenType.WHILE, "while"),
            (TokenType.DO, "do"),
            (TokenType.OD, "od"),
        ]

    def test_for_to_step(self):
        result = lex("FOR TO STEP")
        assert result == [
            (TokenType.FOR, "for"),
            (TokenType.TO, "to"),
            (TokenType.STEP, "step"),
        ]

    def test_until_exit(self):
        result = lex("UNTIL EXIT")
        assert result == [
            (TokenType.UNTIL, "until"),
            (TokenType.EXIT, "exit"),
        ]

    def test_and_or_xor(self):
        result = lex("AND OR XOR")
        assert result == [
            (TokenType.AND, "and"),
            (TokenType.OR, "or"),
            (TokenType.XOR, "xor"),
        ]

    def test_mod_lsh_rsh(self):
        result = lex("MOD LSH RSH")
        assert result == [
            (TokenType.MOD, "mod"),
            (TokenType.LSH, "lsh"),
            (TokenType.RSH, "rsh"),
        ]

    def test_case_insensitive(self):
        """Keywords work regardless of case."""
        assert lex("Byte") == [(TokenType.BYTE, "byte")]
        assert lex("byte") == [(TokenType.BYTE, "byte")]
        assert lex("bYtE") == [(TokenType.BYTE, "byte")]

    def test_pointer_array_type(self):
        result = lex("POINTER ARRAY TYPE")
        assert result == [
            (TokenType.POINTER, "pointer"),
            (TokenType.ARRAY, "array"),
            (TokenType.TYPE, "type"),
        ]

    def test_module_define_set_include(self):
        result = lex("MODULE DEFINE SET INCLUDE")
        assert result == [
            (TokenType.MODULE, "module"),
            (TokenType.DEFINE, "define"),
            (TokenType.SET, "set"),
            (TokenType.INCLUDE, "include"),
        ]

    def test_interrupt(self):
        assert lex("INTERRUPT") == [(TokenType.INTERRUPT, "interrupt")]


# ===========================================================================
# Numbers
# ===========================================================================


class TestTokenizeNumbers:
    """Numeric constants: decimal, hex ($), character (')."""

    def test_decimal(self):
        assert lex("42") == [(TokenType.NUMBER, "42")]

    def test_decimal_zero(self):
        assert lex("0") == [(TokenType.NUMBER, "0")]

    def test_large_decimal(self):
        assert lex("65535") == [(TokenType.NUMBER, "65535")]

    def test_hex(self):
        assert lex("$FF") == [(TokenType.HEX_NUMBER, "$FF")]

    def test_hex_lowercase(self):
        assert lex("$ff") == [(TokenType.HEX_NUMBER, "$ff")]

    def test_hex_address(self):
        assert lex("$D000") == [(TokenType.HEX_NUMBER, "$D000")]

    def test_char_const(self):
        assert lex("'A") == [(TokenType.CHAR_CONST, "'A")]

    def test_char_const_digit(self):
        assert lex("'0") == [(TokenType.CHAR_CONST, "'0")]

    def test_char_const_space(self):
        assert lex("' ") == [(TokenType.CHAR_CONST, "' ")]


# ===========================================================================
# Strings
# ===========================================================================


class TestTokenizeStrings:
    """String constants with double-quote escaping."""

    def test_simple_string(self):
        assert lex('"Hello World"') == [(TokenType.STRING, '"Hello World"')]

    def test_empty_string(self):
        assert lex('""') == [(TokenType.STRING, '""')]

    def test_embedded_quote(self):
        result = lex('"A ""quoted"" word"')
        assert result == [(TokenType.STRING, '"A ""quoted"" word"')]

    def test_unterminated_string(self):
        with pytest.raises(LexerError):
            Lexer('"hello').tokenize()


# ===========================================================================
# Operators and Delimiters
# ===========================================================================


class TestTokenizeOperators:
    """All operator and delimiter tokens."""

    def test_arithmetic(self):
        result = lex("+ - * /")
        assert result == [
            (TokenType.PLUS, "+"),
            (TokenType.MINUS, "-"),
            (TokenType.STAR, "*"),
            (TokenType.SLASH, "/"),
        ]

    def test_relational_eq(self):
        assert lex("=") == [(TokenType.EQ, "=")]

    def test_relational_ne(self):
        assert lex("<>") == [(TokenType.NE, "<>")]

    def test_relational_lt_gt(self):
        result = lex("< >")
        assert result == [
            (TokenType.LT, "<"),
            (TokenType.GT, ">"),
        ]

    def test_relational_le_ge(self):
        result = lex("<= >=")
        assert result == [
            (TokenType.LE, "<="),
            (TokenType.GE, ">="),
        ]

    def test_at_caret_percent(self):
        result = lex("@ ^ %")
        assert result == [
            (TokenType.AT, "@"),
            (TokenType.CARET, "^"),
            (TokenType.PERCENT, "%"),
        ]

    def test_parens_comma_dot(self):
        result = lex("( ) , .")
        assert result == [
            (TokenType.LPAREN, "("),
            (TokenType.RPAREN, ")"),
            (TokenType.COMMA, ","),
            (TokenType.DOT, "."),
        ]

    def test_lbracket_rbracket(self):
        result = lex("[ ]")
        assert result == [
            (TokenType.LBRACKET, "["),
            (TokenType.RBRACKET, "]"),
        ]


# ===========================================================================
# Comments
# ===========================================================================


class TestTokenizeComments:
    """Semicolon comments are stripped."""

    def test_line_comment(self):
        assert lex("; this is a comment") == []

    def test_inline_comment(self):
        result = lex("BYTE x ; a variable")
        assert result == [
            (TokenType.BYTE, "byte"),
            (TokenType.IDENTIFIER, "x"),
        ]

    def test_comment_after_number(self):
        result = lex("42 ; the answer")
        assert result == [(TokenType.NUMBER, "42")]


# ===========================================================================
# Identifiers
# ===========================================================================


class TestTokenizeIdentifiers:
    """Identifiers are case-normalized to lowercase."""

    def test_simple(self):
        assert lex("count") == [(TokenType.IDENTIFIER, "count")]

    def test_with_underscore(self):
        assert lex("my_var") == [(TokenType.IDENTIFIER, "my_var")]

    def test_with_digits(self):
        assert lex("x1") == [(TokenType.IDENTIFIER, "x1")]

    def test_case_normalized(self):
        assert lex("MyVar") == [(TokenType.IDENTIFIER, "myvar")]

    def test_not_keyword(self):
        """Identifiers that start like keywords but aren't."""
        assert lex("bytes") == [(TokenType.IDENTIFIER, "bytes")]
        assert lex("integer") == [(TokenType.IDENTIFIER, "integer")]


# ===========================================================================
# Line/Column tracking
# ===========================================================================


class TestLineColumn:
    """Tokens track their source position."""

    def test_first_token_position(self):
        tokens = Lexer("BYTE").tokenize()
        assert tokens[0].line == 1
        assert tokens[0].column == 1

    def test_second_line(self):
        tokens = Lexer("BYTE\nx").tokenize()
        # x is on line 2
        x_tok = [t for t in tokens if t.value == "x"][0]
        assert x_tok.line == 2
        assert x_tok.column == 1

    def test_column_advances(self):
        tokens = Lexer("BYTE x").tokenize()
        x_tok = [t for t in tokens if t.value == "x"][0]
        assert x_tok.line == 1
        assert x_tok.column == 6


# ===========================================================================
# Errors
# ===========================================================================


class TestLexerErrors:
    """Invalid input produces LexerError with position info."""

    def test_unexpected_character(self):
        with pytest.raises(LexerError):
            Lexer("~").tokenize()

    def test_unterminated_string(self):
        with pytest.raises(LexerError):
            Lexer('"hello').tokenize()

    def test_empty_hex(self):
        with pytest.raises(LexerError):
            Lexer("$ ").tokenize()


# ===========================================================================
# Combined expressions
# ===========================================================================


class TestTokenizeCombined:
    """Tokenize realistic Action! fragments."""

    def test_var_declaration(self):
        result = lex("BYTE count=[0]")
        assert result == [
            (TokenType.BYTE, "byte"),
            (TokenType.IDENTIFIER, "count"),
            (TokenType.EQ, "="),
            (TokenType.LBRACKET, "["),
            (TokenType.NUMBER, "0"),
            (TokenType.RBRACKET, "]"),
        ]

    def test_assignment(self):
        result = lex("x = x + 1")
        assert result == [
            (TokenType.IDENTIFIER, "x"),
            (TokenType.EQ, "="),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.PLUS, "+"),
            (TokenType.NUMBER, "1"),
        ]

    def test_proc_header(self):
        result = lex("PROC Main(BYTE a, CARD b)")
        assert result == [
            (TokenType.PROC, "proc"),
            (TokenType.IDENTIFIER, "main"),
            (TokenType.LPAREN, "("),
            (TokenType.BYTE, "byte"),
            (TokenType.IDENTIFIER, "a"),
            (TokenType.COMMA, ","),
            (TokenType.CARD, "card"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.RPAREN, ")"),
        ]

    def test_if_condition(self):
        result = lex("IF x > 10 THEN")
        assert result == [
            (TokenType.IF, "if"),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.GT, ">"),
            (TokenType.NUMBER, "10"),
            (TokenType.THEN, "then"),
        ]

    def test_hex_address_placement(self):
        result = lex("BYTE x=$8000")
        assert result == [
            (TokenType.BYTE, "byte"),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.EQ, "="),
            (TokenType.HEX_NUMBER, "$8000"),
        ]
