"""Parser for SK02-C compiler."""

from typing import Optional

from .ast_nodes import *
from .tokens import Token, TokenType


class ParseError(Exception):
    """Parse error exception."""

    def __init__(self, message: str, token: Token):
        super().__init__(f"Parse error at {token.line}:{token.column}: {message}")
        self.token = token


class Parser:
    """Recursive descent parser for C subset."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        """Get current token."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def peek_token(self, offset: int = 1) -> Token:
        """Peek ahead at token."""
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[pos]

    def advance(self) -> Token:
        """Consume and return current token."""
        token = self.current_token()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Consume token of expected type or raise error."""
        token = self.current_token()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name}", token
            )
        return self.advance()

    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self.current_token().type in token_types

    # Type parsing
    def parse_type(self) -> Type:
        """Parse a type specifier."""
        token = self.current_token()

        # Base type
        if self.match(
            TokenType.CHAR,
            TokenType.INT,
            TokenType.VOID,
            TokenType.UINT8,
            TokenType.INT8,
            TokenType.UINT16,
            TokenType.INT16,
        ):
            type_token = self.advance()
            base_type = BasicType(type_token.value, type_token.line, type_token.column)
        else:
            raise ParseError("Expected type specifier", token)

        # Pointer(s)
        while self.match(TokenType.STAR):
            star = self.advance()
            base_type = PointerType(base_type, star.line, star.column)

        return base_type

    # Expression parsing (precedence climbing)
    def parse_primary_expression(self) -> Expression:
        """Parse primary expression."""
        token = self.current_token()

        # Number literal
        if self.match(TokenType.NUMBER):
            num_token = self.advance()
            value = int(num_token.value, 0)  # Auto-detect base
            return NumberLiteral(value, num_token.line, num_token.column)

        # Character literal
        elif self.match(TokenType.CHAR_LITERAL):
            char_token = self.advance()
            return CharLiteral(char_token.value, char_token.line, char_token.column)

        # String literal
        elif self.match(TokenType.STRING_LITERAL):
            str_token = self.advance()
            return StringLiteral(str_token.value, str_token.line, str_token.column)

        # Identifier or function call
        elif self.match(TokenType.IDENTIFIER):
            ident_token = self.advance()
            # Check for function call
            if self.match(TokenType.LPAREN):
                self.advance()
                args = []
                if not self.match(TokenType.RPAREN):
                    args.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        self.advance()
                        args.append(self.parse_expression())
                self.expect(TokenType.RPAREN)
                return FunctionCall(
                    ident_token.value, args, ident_token.line, ident_token.column
                )
            else:
                return Identifier(ident_token.value, ident_token.line, ident_token.column)

        # Parenthesized expression
        elif self.match(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        else:
            raise ParseError("Expected expression", token)

    def parse_postfix_expression(self) -> Expression:
        """Parse postfix expression (array access, ++, --)."""
        expr = self.parse_primary_expression()

        while True:
            if self.match(TokenType.LBRACKET):
                bracket = self.advance()
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = ArrayAccess(expr, index, bracket.line, bracket.column)
            elif self.match(TokenType.INC, TokenType.DEC):
                op_token = self.advance()
                expr = UnaryOp(
                    op_token.value, expr, True, op_token.line, op_token.column
                )
            else:
                break

        return expr

    def parse_unary_expression(self) -> Expression:
        """Parse unary expression."""
        # Prefix operators
        if self.match(
            TokenType.INC,
            TokenType.DEC,
            TokenType.MINUS,
            TokenType.LNOT,
            TokenType.TILDE,
            TokenType.STAR,
            TokenType.AMPERSAND,
        ):
            op_token = self.advance()
            operand = self.parse_unary_expression()
            return UnaryOp(op_token.value, operand, False, op_token.line, op_token.column)

        return self.parse_postfix_expression()

    def parse_binary_expression(self, min_prec: int = 0) -> Expression:
        """Parse binary expression with precedence climbing."""
        left = self.parse_unary_expression()

        while True:
            token = self.current_token()
            prec = self._get_precedence(token.type)

            if prec < min_prec:
                break

            op_token = self.advance()
            right = self.parse_binary_expression(prec + 1)
            left = BinaryOp(op_token.value, left, right, op_token.line, op_token.column)

        return left

    def _get_precedence(self, token_type: TokenType) -> int:
        """Get operator precedence."""
        precedence_map = {
            TokenType.LOR: 1,
            TokenType.LAND: 2,
            TokenType.PIPE: 3,
            TokenType.CARET: 4,
            TokenType.AMPERSAND: 5,
            TokenType.EQ: 6,
            TokenType.NE: 6,
            TokenType.LT: 7,
            TokenType.GT: 7,
            TokenType.LE: 7,
            TokenType.GE: 7,
            TokenType.LSHIFT: 8,
            TokenType.RSHIFT: 8,
            TokenType.PLUS: 9,
            TokenType.MINUS: 9,
            TokenType.STAR: 10,
            TokenType.SLASH: 10,
            TokenType.PERCENT: 10,
        }
        return precedence_map.get(token_type, -1)

    def parse_assignment_expression(self) -> Expression:
        """Parse assignment or regular expression."""
        expr = self.parse_binary_expression()

        # Check for assignment operators
        if self.match(
            TokenType.ASSIGN,
            TokenType.PLUS_ASSIGN,
            TokenType.MINUS_ASSIGN,
            TokenType.AND_ASSIGN,
            TokenType.OR_ASSIGN,
            TokenType.XOR_ASSIGN,
        ):
            op_token = self.advance()
            value = self.parse_assignment_expression()
            return Assignment(expr, op_token.value, value, op_token.line, op_token.column)

        return expr

    def parse_expression(self) -> Expression:
        """Parse full expression."""
        return self.parse_assignment_expression()

    # Statement parsing
    def parse_statement(self) -> Statement:
        """Parse a statement."""
        token = self.current_token()

        # Compound statement
        if self.match(TokenType.LBRACE):
            return self.parse_compound_statement()

        # Return statement
        elif self.match(TokenType.RETURN):
            return_token = self.advance()
            value = None
            if not self.match(TokenType.SEMICOLON):
                value = self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            return ReturnStatement(value, return_token.line, return_token.column)

        # If statement
        elif self.match(TokenType.IF):
            if_token = self.advance()
            self.expect(TokenType.LPAREN)
            condition = self.parse_expression()
            self.expect(TokenType.RPAREN)
            then_stmt = self.parse_statement()
            else_stmt = None
            if self.match(TokenType.ELSE):
                self.advance()
                else_stmt = self.parse_statement()
            return IfStatement(
                condition, then_stmt, else_stmt, if_token.line, if_token.column
            )

        # While loop
        elif self.match(TokenType.WHILE):
            while_token = self.advance()
            self.expect(TokenType.LPAREN)
            condition = self.parse_expression()
            self.expect(TokenType.RPAREN)
            body = self.parse_statement()
            return WhileStatement(condition, body, while_token.line, while_token.column)

        # For loop
        elif self.match(TokenType.FOR):
            for_token = self.advance()
            self.expect(TokenType.LPAREN)
            init = None if self.match(TokenType.SEMICOLON) else self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            cond = None if self.match(TokenType.SEMICOLON) else self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            incr = None if self.match(TokenType.RPAREN) else self.parse_expression()
            self.expect(TokenType.RPAREN)
            body = self.parse_statement()
            return ForStatement(init, cond, incr, body, for_token.line, for_token.column)

        # Break
        elif self.match(TokenType.BREAK):
            break_token = self.advance()
            self.expect(TokenType.SEMICOLON)
            return BreakStatement(break_token.line, break_token.column)

        # Continue
        elif self.match(TokenType.CONTINUE):
            cont_token = self.advance()
            self.expect(TokenType.SEMICOLON)
            return ContinueStatement(cont_token.line, cont_token.column)

        # Variable declaration
        elif self.match(
            TokenType.CHAR,
            TokenType.INT,
            TokenType.STATIC,
            TokenType.REGISTER,
            TokenType.UINT8,
            TokenType.INT8,
            TokenType.UINT16,
            TokenType.INT16,
        ):
            return self.parse_variable_declaration()

        # Expression statement
        else:
            expr = None
            if not self.match(TokenType.SEMICOLON):
                expr = self.parse_expression()
            semi = self.expect(TokenType.SEMICOLON)
            return ExpressionStatement(expr, semi.line, semi.column)

    def parse_compound_statement(self) -> CompoundStatement:
        """Parse compound statement (block)."""
        lbrace = self.expect(TokenType.LBRACE)
        statements = []

        while not self.match(TokenType.RBRACE) and not self.match(TokenType.EOF):
            statements.append(self.parse_statement())

        self.expect(TokenType.RBRACE)
        return CompoundStatement(statements, lbrace.line, lbrace.column)

    # Declaration parsing
    def parse_variable_declaration(self) -> VariableDeclaration:
        """Parse variable declaration."""
        is_static = False
        is_register = False

        # Storage class
        if self.match(TokenType.STATIC):
            self.advance()
            is_static = True
        elif self.match(TokenType.REGISTER):
            self.advance()
            is_register = True

        # Type
        var_type = self.parse_type()

        # Name
        name_token = self.expect(TokenType.IDENTIFIER)

        # Array?
        if self.match(TokenType.LBRACKET):
            self.advance()
            size = None
            if not self.match(TokenType.RBRACKET):
                size_expr = self.parse_expression()
                if isinstance(size_expr, NumberLiteral):
                    size = size_expr.value
                else:
                    raise ParseError("Array size must be constant", name_token)
            self.expect(TokenType.RBRACKET)
            var_type = ArrayType(var_type, size, name_token.line, name_token.column)

        # Initializer
        initializer = None
        if self.match(TokenType.ASSIGN):
            self.advance()
            initializer = self.parse_expression()

        self.expect(TokenType.SEMICOLON)

        return VariableDeclaration(
            var_type,
            name_token.value,
            initializer,
            is_static,
            is_register,
            False,
            name_token.line,
            name_token.column,
        )

    def parse_function_declaration(self) -> FunctionDeclaration:
        """Parse function declaration."""
        # Return type
        return_type = self.parse_type()

        # Function name
        name_token = self.expect(TokenType.IDENTIFIER)

        # Parameters
        self.expect(TokenType.LPAREN)
        parameters = []

        if not self.match(TokenType.RPAREN):
            # Parse parameter list
            param_type = self.parse_type()
            param_name_token = self.expect(TokenType.IDENTIFIER)
            parameters.append(
                Parameter(
                    param_type,
                    param_name_token.value,
                    param_name_token.line,
                    param_name_token.column,
                )
            )

            while self.match(TokenType.COMMA):
                self.advance()
                param_type = self.parse_type()
                param_name_token = self.expect(TokenType.IDENTIFIER)
                parameters.append(
                    Parameter(
                        param_type,
                        param_name_token.value,
                        param_name_token.line,
                        param_name_token.column,
                    )
                )

        self.expect(TokenType.RPAREN)

        # Function body or just declaration
        body = None
        if self.match(TokenType.LBRACE):
            body = self.parse_compound_statement()
        else:
            self.expect(TokenType.SEMICOLON)

        return FunctionDeclaration(
            return_type,
            name_token.value,
            parameters,
            body,
            name_token.line,
            name_token.column,
        )

    def parse_program(self) -> Program:
        """Parse entire program."""
        declarations = []

        while not self.match(TokenType.EOF):
            # Try to determine if it's a variable or function declaration
            # by looking ahead past the type
            saved_pos = self.pos

            # Skip type
            self.parse_type()

            # Get name
            self.expect(TokenType.IDENTIFIER)

            # Check what follows
            is_function = self.match(TokenType.LPAREN)

            # Restore position
            self.pos = saved_pos

            # Parse declaration
            if is_function:
                declarations.append(self.parse_function_declaration())
            else:
                declarations.append(self.parse_variable_declaration())

        return Program(declarations, 1, 1)
