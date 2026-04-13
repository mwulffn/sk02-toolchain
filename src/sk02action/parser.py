"""Recursive descent parser for the SK-02 Action! compiler."""

from .ast_nodes import (
    ArrayAccess,
    ArrayType,
    AssignmentStmt,
    BinaryOp,
    ByteType,
    CardType,
    CharConstant,
    Declaration,
    Dereference,
    DoLoop,
    ExitStmt,
    Expression,
    ForLoop,
    FuncDecl,
    FunctionCall,
    Identifier,
    IfStmt,
    IntType,
    NumberLiteral,
    Parameter,
    PointerType,
    ProcCall,
    ProcDecl,
    Program,
    ReturnStmt,
    SetDirective,
    Statement,
    StringLiteral,
    Type,
    UnaryOp,
    UntilLoop,
    VarDecl,
    WhileLoop,
)
from .tokens import Token, TokenType


class ParseError(Exception):
    """Parse error with source position."""

    def __init__(self, message: str, token: Token):
        super().__init__(f"Parse error at {token.line}:{token.column}: {message}")
        self.token = token


class Parser:
    """Recursive descent parser for Action! source code."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self._array_names: set[str] = set()  # names declared as ARRAY

    # ------------------------------------------------------------------
    # Token access
    # ------------------------------------------------------------------

    def _current(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[pos]

    def _advance(self) -> Token:
        token = self._current()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        token = self._current()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name} ({token.value!r})",
                token,
            )
        return self._advance()

    def _match(self, *types: TokenType) -> bool:
        return self._current().type in types

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse_program(self) -> Program:
        """Parse the entire program."""
        tok = self._current()
        declarations: list[Declaration] = []
        directives: list[SetDirective] = []

        while not self._match(TokenType.EOF):
            if self._match(TokenType.SET):
                directives.append(self._parse_set_directive())
            else:
                decl = self._parse_top_level()
                if isinstance(decl, list):
                    declarations.extend(decl)
                else:
                    declarations.append(decl)

        return Program(declarations, tok.line, tok.column, directives)

    def _parse_top_level(self) -> Declaration | list[Declaration]:
        """Parse a top-level declaration (var, proc, or func)."""
        tok = self._current()

        if tok.type == TokenType.PROC:
            return self._parse_proc_decl()
        elif tok.type in (
            TokenType.BYTE,
            TokenType.CHAR,
            TokenType.CARD,
            TokenType.INT,
        ):
            # Could be: type var_list  OR  type FUNC name(...)
            if self._peek().type == TokenType.FUNC:
                return self._parse_func_decl()
            else:
                return self._parse_var_decl_list()
        else:
            raise ParseError(f"Expected declaration, got {tok.type.name}", tok)

    # ------------------------------------------------------------------
    # Type parsing
    # ------------------------------------------------------------------

    def _parse_type(self) -> Type:
        tok = self._current()
        if tok.type in (TokenType.BYTE, TokenType.CHAR):
            self._advance()
            base: Type = ByteType(tok.line, tok.column)
        elif tok.type == TokenType.CARD:
            self._advance()
            base = CardType(tok.line, tok.column)
        elif tok.type == TokenType.INT:
            self._advance()
            base = IntType(tok.line, tok.column)
        else:
            raise ParseError(f"Expected type, got {tok.type.name}", tok)

        if self._match(TokenType.POINTER):
            self._advance()
            return PointerType(base, tok.line, tok.column)
        if self._match(TokenType.ARRAY):
            self._advance()
            # Size will be filled in by _parse_var_item after the variable name
            return ArrayType(base, 0, tok.line, tok.column)
        return base

    # ------------------------------------------------------------------
    # Variable declarations
    # ------------------------------------------------------------------

    def _parse_var_decl_list(self) -> list[VarDecl]:
        """Parse: type ident [=addr] [=[val]] {, ident [=addr] [=[val]]}"""
        var_type = self._parse_type()
        decls = [self._parse_var_item(var_type)]

        while self._match(TokenType.COMMA):
            self._advance()  # consume ','
            decls.append(self._parse_var_item(var_type))

        return decls

    def _parse_var_item(self, var_type: Type) -> VarDecl:
        """Parse a single variable item: ident [=addr] [=[val]]"""
        tok = self._expect(TokenType.IDENTIFIER)
        name = tok.value
        address = None
        initial_value = None

        initial_values = None

        if isinstance(var_type, ArrayType):
            if self._match(TokenType.LPAREN):
                # name(size) [=addr]
                self._expect(TokenType.LPAREN)
                size = self._parse_const_value()
                self._expect(TokenType.RPAREN)
                var_type = ArrayType(
                    var_type.base_type, size, var_type.line, var_type.column
                )
                self._array_names.add(name)
                if self._match(TokenType.EQ):
                    self._advance()
                    address = self._parse_const_value()
            elif self._match(TokenType.EQ):
                self._advance()  # consume '='
                if self._match(TokenType.LBRACKET):
                    # name = [v1 v2 ...]
                    self._advance()  # consume '['
                    values: list[int] = []
                    while not self._match(TokenType.RBRACKET):
                        values.append(self._parse_const_value())
                    self._expect(TokenType.RBRACKET)
                    var_type = ArrayType(
                        var_type.base_type, len(values), var_type.line, var_type.column
                    )
                    self._array_names.add(name)
                    initial_values = values
                elif self._match(TokenType.STRING):
                    # name = "string"
                    tok_str = self._advance()
                    s = self._decode_string_token(tok_str)
                    if len(s) > 255:
                        raise ParseError("String literal too long (max 255)", tok_str)
                    bytes_data = [len(s)] + [ord(c) for c in s]
                    var_type = ArrayType(
                        var_type.base_type,
                        len(bytes_data),
                        var_type.line,
                        var_type.column,
                    )
                    self._array_names.add(name)
                    initial_values = bytes_data
                else:
                    # name = addr
                    address = self._parse_const_value()
                    var_type = ArrayType(
                        var_type.base_type, 0, var_type.line, var_type.column
                    )
                    self._array_names.add(name)
        else:
            if self._match(TokenType.EQ):
                self._advance()  # consume '='
                if self._match(TokenType.LBRACKET):
                    # =[value]
                    self._advance()  # consume '['
                    initial_value = self._parse_const_value()
                    self._expect(TokenType.RBRACKET)
                else:
                    # =address (decimal or hex constant)
                    address = self._parse_const_value()
                    # Check if followed by =[value] (address + initializer)
                    if self._match(TokenType.EQ):
                        self._advance()
                        if self._match(TokenType.LBRACKET):
                            self._advance()
                            initial_value = self._parse_const_value()
                            self._expect(TokenType.RBRACKET)

        return VarDecl(
            var_type, name, address, initial_value, tok.line, tok.column, initial_values
        )

    def _parse_const_value(self) -> int:
        """Parse a numeric constant (decimal or hex)."""
        tok = self._current()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return int(tok.value)
        elif tok.type == TokenType.HEX_NUMBER:
            self._advance()
            return int(tok.value[1:], 16)  # strip '$'
        else:
            raise ParseError(f"Expected numeric constant, got {tok.type.name}", tok)

    @staticmethod
    def _decode_string_token(tok: "Token") -> str:
        """Decode a STRING token value to a plain Python string.

        The lexer stores the raw quoted form including surrounding quotes.
        This strips the outer quotes and unescapes "" → ".
        """
        raw = tok.value  # e.g. '"Hello ""world"""'
        return raw[1:-1].replace('""', '"')

    def _parse_set_directive(self) -> SetDirective:
        """Parse: SET const_expr = (const_value | identifier)"""
        tok = self._expect(TokenType.SET)
        target = self._parse_const_value()
        self._expect(TokenType.EQ)
        if self._match(TokenType.IDENTIFIER):
            val_tok = self._advance()
            value: int | str = val_tok.value  # identifier name
        else:
            value = self._parse_const_value()
        return SetDirective(target, value, tok.line, tok.column)

    # ------------------------------------------------------------------
    # PROC declaration
    # ------------------------------------------------------------------

    def _parse_proc_decl(self) -> ProcDecl:
        tok = self._expect(TokenType.PROC)
        name_tok = self._expect(TokenType.IDENTIFIER)
        name = name_tok.value

        # Parameters
        self._expect(TokenType.LPAREN)
        params = self._parse_param_list()
        self._expect(TokenType.RPAREN)

        # Local declarations
        locals_ = self._parse_local_decls()

        # Body statements (up to final RETURN)
        body = self._parse_stmt_list(stop_at={TokenType.RETURN})

        # Final RETURN
        self._expect(TokenType.RETURN)

        return ProcDecl(name, params, locals_, body, tok.line, tok.column)

    # ------------------------------------------------------------------
    # FUNC declaration
    # ------------------------------------------------------------------

    def _parse_func_decl(self) -> FuncDecl:
        return_type = self._parse_type()
        tok = self._expect(TokenType.FUNC)
        name_tok = self._expect(TokenType.IDENTIFIER)
        name = name_tok.value

        # Parameters
        self._expect(TokenType.LPAREN)
        params = self._parse_param_list()
        self._expect(TokenType.RPAREN)

        # Local declarations
        locals_ = self._parse_local_decls()

        # Body statements (up to final RETURN)
        body = self._parse_stmt_list(stop_at={TokenType.RETURN})

        # Final RETURN(expr)
        self._expect(TokenType.RETURN)
        self._expect(TokenType.LPAREN)
        return_value = self._parse_expression()
        self._expect(TokenType.RPAREN)

        return FuncDecl(
            return_type,
            name,
            params,
            locals_,
            body,
            return_value,
            tok.line,
            tok.column,
        )

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def _parse_param_list(self) -> list[Parameter]:
        params: list[Parameter] = []
        if self._match(TokenType.RPAREN):
            return params

        params.append(self._parse_param())
        while self._match(TokenType.COMMA):
            self._advance()
            params.append(self._parse_param())
        return params

    def _parse_param(self) -> Parameter:
        param_type = self._parse_type()
        tok = self._expect(TokenType.IDENTIFIER)
        return Parameter(param_type, tok.value, tok.line, tok.column)

    # ------------------------------------------------------------------
    # Local declarations
    # ------------------------------------------------------------------

    def _parse_local_decls(self) -> list[VarDecl]:
        """Parse local variable declarations at top of routine body."""
        locals_: list[VarDecl] = []
        while self._match(
            TokenType.BYTE, TokenType.CHAR, TokenType.CARD, TokenType.INT
        ):
            # Make sure this isn't a FUNC declaration (type FUNC ...)
            if self._peek().type == TokenType.FUNC:
                break
            locals_.extend(self._parse_var_decl_list())
        return locals_

    # ------------------------------------------------------------------
    # Statement list
    # ------------------------------------------------------------------

    def _parse_stmt_list(self, stop_at: set[TokenType]) -> list[Statement]:
        """Parse statements until a stop token is reached."""
        stmts: list[Statement] = []
        while not self._match(TokenType.EOF) and self._current().type not in stop_at:
            stmts.append(self._parse_statement())
        return stmts

    def _parse_statement(self) -> Statement:
        tok = self._current()

        if tok.type == TokenType.IF:
            return self._parse_if_stmt()
        elif tok.type == TokenType.WHILE:
            return self._parse_while_loop()
        elif tok.type == TokenType.DO:
            return self._parse_do_loop()
        elif tok.type == TokenType.UNTIL:
            return self._parse_until_loop()
        elif tok.type == TokenType.FOR:
            return self._parse_for_loop()
        elif tok.type == TokenType.EXIT:
            self._advance()
            return ExitStmt(tok.line, tok.column)
        elif tok.type == TokenType.RETURN:
            return self._parse_return_stmt()
        elif tok.type == TokenType.IDENTIFIER:
            return self._parse_ident_statement()
        else:
            raise ParseError(
                f"Expected statement, got {tok.type.name} ({tok.value!r})", tok
            )

    def _parse_ident_statement(self) -> Statement:
        """Parse assignment or proc call starting with an identifier."""
        tok = self._current()
        name = tok.value

        # Check for array element assignment: array_name(index) = expr
        if self._peek().type == TokenType.LPAREN and name in self._array_names:
            self._advance()  # consume identifier
            self._advance()  # consume '('
            index = self._parse_expression()
            self._expect(TokenType.RPAREN)
            self._expect(TokenType.EQ)
            value = self._parse_expression()
            target: Expression = ArrayAccess(name, index, tok.line, tok.column)
            return AssignmentStmt(target, value, tok.line, tok.column)

        # Peek ahead: if '(' follows, it's a proc call
        if self._peek().type == TokenType.LPAREN:
            self._advance()  # consume identifier
            self._advance()  # consume '('
            args = self._parse_arg_list()
            self._expect(TokenType.RPAREN)
            return ProcCall(name, args, tok.line, tok.column)

        # Check for pointer dereference as lvalue: ident^ = expr
        if self._peek().type == TokenType.CARET:
            self._advance()  # consume identifier
            self._advance()  # consume '^'
            target = Dereference(
                Identifier(name, tok.line, tok.column), tok.line, tok.column
            )
            self._expect(TokenType.EQ)
            value = self._parse_expression()
            return AssignmentStmt(target, value, tok.line, tok.column)

        # Otherwise it's a plain assignment: ident = expr
        self._advance()  # consume identifier
        self._expect(TokenType.EQ)
        value = self._parse_expression()
        return AssignmentStmt(
            Identifier(name, tok.line, tok.column),
            value,
            tok.line,
            tok.column,
        )

    def _parse_arg_list(self) -> list[Expression]:
        args: list[Expression] = []
        if self._match(TokenType.RPAREN):
            return args
        args.append(self._parse_expression())
        while self._match(TokenType.COMMA):
            self._advance()
            args.append(self._parse_expression())
        return args

    # ------------------------------------------------------------------
    # IF statement
    # ------------------------------------------------------------------

    def _parse_if_stmt(self) -> IfStmt:
        tok = self._expect(TokenType.IF)
        condition = self._parse_expression()
        self._expect(TokenType.THEN)

        then_body = self._parse_stmt_list(
            stop_at={TokenType.ELSEIF, TokenType.ELSE, TokenType.FI}
        )

        elseif_clauses: list[tuple[Expression, list[Statement]]] = []
        while self._match(TokenType.ELSEIF):
            self._advance()
            ei_cond = self._parse_expression()
            self._expect(TokenType.THEN)
            ei_body = self._parse_stmt_list(
                stop_at={TokenType.ELSEIF, TokenType.ELSE, TokenType.FI}
            )
            elseif_clauses.append((ei_cond, ei_body))

        else_body = None
        if self._match(TokenType.ELSE):
            self._advance()
            else_body = self._parse_stmt_list(stop_at={TokenType.FI})

        self._expect(TokenType.FI)

        return IfStmt(
            condition,
            then_body,
            elseif_clauses,
            else_body,
            tok.line,
            tok.column,
        )

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------

    def _parse_while_loop(self) -> WhileLoop:
        tok = self._expect(TokenType.WHILE)
        condition = self._parse_expression()
        self._expect(TokenType.DO)
        body = self._parse_stmt_list(stop_at={TokenType.OD})
        self._expect(TokenType.OD)
        return WhileLoop(condition, body, tok.line, tok.column)

    def _parse_do_loop(self) -> DoLoop:
        tok = self._expect(TokenType.DO)
        body = self._parse_stmt_list(stop_at={TokenType.OD})
        self._expect(TokenType.OD)
        return DoLoop(body, tok.line, tok.column)

    def _parse_until_loop(self) -> UntilLoop:
        tok = self._expect(TokenType.UNTIL)
        condition = self._parse_expression()
        self._expect(TokenType.DO)
        body = self._parse_stmt_list(stop_at={TokenType.OD})
        self._expect(TokenType.OD)
        return UntilLoop(condition, body, tok.line, tok.column)

    def _parse_for_loop(self) -> ForLoop:
        tok = self._expect(TokenType.FOR)
        var_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.EQ)
        start = self._parse_expression()
        self._expect(TokenType.TO)
        limit = self._parse_expression()
        step = None
        if self._match(TokenType.STEP):
            self._advance()
            step = self._parse_expression()
        self._expect(TokenType.DO)
        body = self._parse_stmt_list(stop_at={TokenType.OD})
        self._expect(TokenType.OD)
        return ForLoop(var_tok.value, start, limit, step, body, tok.line, tok.column)

    # ------------------------------------------------------------------
    # RETURN statement (early return within body)
    # ------------------------------------------------------------------

    def _parse_return_stmt(self) -> ReturnStmt:
        tok = self._expect(TokenType.RETURN)
        value = None
        if self._match(TokenType.LPAREN):
            self._advance()
            value = self._parse_expression()
            self._expect(TokenType.RPAREN)
        return ReturnStmt(value, tok.line, tok.column)

    # ------------------------------------------------------------------
    # Expressions (precedence climbing)
    # ------------------------------------------------------------------

    def _parse_expression(self) -> Expression:
        """expr = and_expr { (OR | XOR) and_expr }"""
        left = self._parse_and_expr()
        while self._match(TokenType.OR, TokenType.XOR):
            op_tok = self._advance()
            right = self._parse_and_expr()
            left = BinaryOp(op_tok.value, left, right, op_tok.line, op_tok.column)
        return left

    def _parse_and_expr(self) -> Expression:
        """and_expr = rel_expr { AND rel_expr }"""
        left = self._parse_rel_expr()
        while self._match(TokenType.AND):
            op_tok = self._advance()
            right = self._parse_rel_expr()
            left = BinaryOp(op_tok.value, left, right, op_tok.line, op_tok.column)
        return left

    def _parse_rel_expr(self) -> Expression:
        """rel_expr = add_expr { rel_op add_expr }"""
        left = self._parse_add_expr()
        while self._match(
            TokenType.EQ,
            TokenType.NE,
            TokenType.LT,
            TokenType.GT,
            TokenType.LE,
            TokenType.GE,
        ):
            op_tok = self._advance()
            right = self._parse_add_expr()
            left = BinaryOp(op_tok.value, left, right, op_tok.line, op_tok.column)
        return left

    def _parse_add_expr(self) -> Expression:
        """add_expr = mul_expr { ('+' | '-') mul_expr }"""
        left = self._parse_mul_expr()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_mul_expr()
            left = BinaryOp(op_tok.value, left, right, op_tok.line, op_tok.column)
        return left

    def _parse_mul_expr(self) -> Expression:
        """mul_expr = unary_expr { ('*' | '/' | MOD | LSH | RSH) unary_expr }"""
        left = self._parse_unary_expr()
        while self._match(
            TokenType.STAR, TokenType.SLASH, TokenType.MOD, TokenType.LSH, TokenType.RSH
        ):
            op_tok = self._advance()
            right = self._parse_unary_expr()
            left = BinaryOp(op_tok.value, left, right, op_tok.line, op_tok.column)
        return left

    def _parse_unary_expr(self) -> Expression:
        """unary_expr = ['-' | '@' | '%'] primary"""
        if self._match(TokenType.MINUS, TokenType.AT, TokenType.PERCENT):
            op_tok = self._advance()
            operand = self._parse_primary()
            return UnaryOp(op_tok.value, operand, op_tok.line, op_tok.column)
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        """primary = number | hex | char_const | ident ['(' args ')'] | '(' expr ')'"""
        tok = self._current()

        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberLiteral(int(tok.value), tok.line, tok.column)

        elif tok.type == TokenType.HEX_NUMBER:
            self._advance()
            return NumberLiteral(int(tok.value[1:], 16), tok.line, tok.column)

        elif tok.type == TokenType.CHAR_CONST:
            self._advance()
            return CharConstant(ord(tok.value[1]), tok.line, tok.column)

        elif tok.type == TokenType.IDENTIFIER:
            self._advance()
            name = tok.value
            # Check for array access: array_name '(' index ')'
            if self._match(TokenType.LPAREN) and name in self._array_names:
                self._advance()  # consume '('
                index = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return ArrayAccess(name, index, tok.line, tok.column)
            # Check for function call: ident '(' args ')'
            if self._match(TokenType.LPAREN):
                self._advance()  # consume '('
                args = self._parse_arg_list()
                self._expect(TokenType.RPAREN)
                return FunctionCall(name, args, tok.line, tok.column)
            ident = Identifier(name, tok.line, tok.column)
            # Check for postfix dereference: ident^
            if self._match(TokenType.CARET):
                self._advance()
                return Dereference(ident, tok.line, tok.column)
            return ident

        elif tok.type == TokenType.STRING:
            self._advance()
            s = self._decode_string_token(tok)
            return StringLiteral(s, tok.line, tok.column)

        elif tok.type == TokenType.LPAREN:
            self._advance()  # consume '('
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        else:
            raise ParseError(
                f"Expected expression, got {tok.type.name} ({tok.value!r})", tok
            )
