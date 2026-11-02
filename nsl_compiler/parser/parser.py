from ..lexer import Token
from nsl_compiler import libast


class Parser:

    def __init__(self):
        self.tokens: list[Token] = []
        self.position: int = 0
        self.errors: list[str] = []
        self.symbols: dict[str, str] = {}
        self.loop_depth: int = 0

    def _peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.position + offset, len(self.tokens) - 1)]

    def _advance(self, kind: str = None) -> Token:
        token = self._peek()

        if kind is not None and token.kind != kind:
            self._error(token, f"expected {kind}, found {token.kind}")
            return token

        if token.kind != "EOF":
            self.position += 1

        return token

    def _error(self, token: Token, message: str) -> None:
        self.errors.append(
            f"Error: line {token.line}, column {token.column}: {message}"
        )

    def _finish_statement(self, force: bool = False) -> None:
        if self._peek().kind == "SEMI":
            self._advance()
            return

        if not force:
            self._error(self._peek(), "expected ';' after statement")

        while self._peek().kind not in {"SEMI", "RBRACE", "EOF"}:
            self._advance()

        if self._peek().kind == "SEMI":
            self._advance()

    def _parse_expression(self) -> libast.ASTNode:
        return self._parse_logical_or_expression()

    def _parse_logical_or_expression(self) -> libast.ASTNode:
        expression = self._parse_logical_and_expression()
        while self._peek().kind == "OR":
            operator = self._advance()
            right = self._parse_logical_and_expression()
            expression = libast.LogicalOrExpr(
                elems=[expression, right], **operator.location
            )
        return expression

    def _parse_logical_and_expression(self) -> libast.ASTNode:
        expression = self._parse_equality_expression()
        while self._peek().kind == "AND":
            operator = self._advance()
            right = self._parse_equality_expression()
            expression = libast.LogicalAndExpr(
                elems=[expression, right], **operator.location
            )
        return expression

    def _parse_equality_expression(self) -> libast.ASTNode:
        expression = self._parse_relational_expression()
        while self._peek().kind in {"EQ", "NE"}:
            operator = self._advance()
            right = self._parse_relational_expression()
            expression = libast.EqExpr(
                subtype=operator.kind.lower(),
                elems=[expression, right],
                **operator.location,
            )
        return expression

    def _parse_relational_expression(self) -> libast.ASTNode:
        expression = self._parse_additive_expression()
        while self._peek().kind in {"LT", "GT", "LE", "GE"}:
            operator = self._advance()
            right = self._parse_additive_expression()
            expression = libast.RelExpr(
                subtype="s" + operator.kind.lower(),
                elems=[expression, right],
                **operator.location,
            )
        return expression

    def _parse_additive_expression(self) -> libast.ASTNode:
        expression = self._parse_multiplicative_expression()
        while self._peek().kind in {"PLUS", "MINUS"}:
            operator = self._advance()
            right = self._parse_multiplicative_expression()
            node_type = libast.AddExpr if operator.kind == "PLUS" else libast.SubExpr
            expression = node_type(elems=[expression, right], **operator.location)
        return expression

    def _parse_multiplicative_expression(self) -> libast.ASTNode:
        expression = self._parse_unary_expression()
        while self._peek().kind in {"MULT", "DIV"}:
            operator = self._advance()
            right = self._parse_unary_expression()
            node_type = libast.MulExpr if operator.kind == "MULT" else libast.DivExpr
            expression = node_type(elems=[expression, right], **operator.location)
        return expression

    def _parse_unary_expression(self) -> libast.ASTNode:
        if self._peek().kind == "MINUS":
            operator = self._advance()
            return libast.UnaryMinus(
                elems=[self._parse_unary_expression()], **operator.location
            )
        elif self._peek().kind == "NOT":
            operator = self._advance()
            return libast.LogicalNegate(
                elems=[self._parse_unary_expression()], **operator.location
            )

        return self._parse_primary_expression()

    def _parse_primary_expression(self) -> libast.ASTNode:
        token = self._advance()
        match token.kind:
            case "INT":
                return libast.IntLiteral(value=int(token.value), **token.location)
            case "TRUE" | "FALSE":
                return libast.BoolLiteral(value=token.kind == "TRUE", **token.location)
            case "IDENT":
                if token.value not in self.symbols:
                    self._error(token, f"undeclared variable '{token.value}'")
                return libast.Ident(value=token.value, **token.location)
            case "LPAREN":
                expression = self._parse_expression()
                if self._peek().kind == "RPAREN":
                    self._advance()
                    return expression

                self._error(self._peek(), "expected ')' after expression")
                return libast.Error(**self._peek().location)
            case _:
                self._error(token, f"expected expression, found {token.kind}")
                return libast.Error(**token.location)

    def _parse_statement(self) -> libast.ASTNode:
        first_token = self._peek()

        match first_token.kind:
            case "LBRACE":
                opening_token = self._advance()
                statements = []
                while self._peek().kind not in {"RBRACE", "EOF"}:
                    statements.append(self._parse_statement())

                self._advance("RBRACE")

                return libast.Block(
                    elems=statements,
                    **opening_token.location,
                )
            case "RETURN":
                self._advance()
                statement = libast.ReturnStatement(
                    elems=[self._parse_expression()], **first_token.location
                )
            case "VAL" | "VAR":
                self._advance()
                name = self._advance("IDENT")

                if name.kind != "IDENT":
                    self._finish_statement()
                    return libast.Error(**first_token.location)

                if (_assign_statement := self._advance("ASSIGN")).kind != "ASSIGN":
                    expression = libast.Error(**_assign_statement.location)
                else:
                    expression = self._parse_expression()

                statement = libast.DeclarationStatement(
                    subtype=first_token.kind,
                    elems=[libast.Ident(value=name.value, **name.location), expression],
                    **first_token.location,
                )

                if name.value in self.symbols:
                    self._error(name, f"variable '{name.value}' is already declared")
                else:
                    self.symbols[name.value] = first_token.kind

            case "IDENT" if self._peek(1).kind == "ASSIGN":
                name = self._advance()
                assign_token = self._advance()

                statement = libast.AssignmentStatement(
                    elems=[
                        libast.Ident(value=name.value, **name.location),
                        self._parse_expression(),
                    ],
                    **assign_token.location,
                )

                if name.value not in self.symbols:
                    self._error(
                        name, f"assignment to undeclared variable '{name.value}'"
                    )
                elif self.symbols[name.value] == "VAL":
                    self._error(name, f"cannot assign to val '{name.value}'")
            case "IF" | "WHILE":
                if_token = self._advance()

                if (lparen := self._peek(0)).kind != "LPAREN":
                    self._error(
                        lparen,
                        f"Expected left parenthesis in '{if_token.value}' statement, found '{lparen.kind}'",
                    )
                    if lparen.kind not in {"LBRACE", "RBRACE", "SEMI", "EOF"}:
                        self._parse_expression()  # Try parsing invalid condition
                    condition = libast.Error(**self._peek().location)
                else:
                    condition = self._parse_primary_expression()

                if if_token.kind == "WHILE":
                    self.loop_depth += 1
                    try:
                        body = self._parse_statement()
                    finally:
                        self.loop_depth -= 1
                    return libast.WhileStatement(
                        elems=[condition, body], **if_token.location
                    )

                elems = [condition, self._parse_statement()]
                if self._peek().kind == "ELSE":
                    self._advance()
                    elems.append(self._parse_statement())

                return libast.IfStatement(elems=elems, **if_token.location)
            case "ELSE":
                self._advance()
                self._error(
                    first_token, "Standalone 'else' without 'if' is not allowed"
                )
                statement = libast.Error(**first_token.location)
            case "BREAK" | "CONTINUE":
                self._advance()
                if self.loop_depth == 0:
                    self._error(first_token, f"'{first_token.value}' outside a loop")
                node_type = (
                    libast.BreakStatement
                    if first_token.kind == "BREAK"
                    else libast.ContinueStatement
                )
                statement = node_type(**first_token.location)
            case _:
                statement = self._parse_expression()

        self._finish_statement()
        return statement

    def parse(self, tokens: list[Token]) -> tuple[libast.Program, bool]:

        assert tokens

        self.tokens = list(tokens)
        self.position = 0
        self.errors = []
        self.symbols = {}
        self.loop_depth = 0

        if self.tokens[-1].kind != "EOF":
            last = self.tokens[-1]
            self.tokens.append(
                Token("EOF", line=last.line, column=last.column + len(last.value or ""))
            )

        program = libast.Program(**self._peek().location)
        while self._peek().kind != "EOF":
            program.elems.append(self._parse_statement())

        if not program.elems:
            self._error(self._peek(), "expected at least one statement")
        elif not isinstance(program.elems[-1], libast.ReturnStatement):
            self._error(self._peek(), "the last statement must be a return statement")

        return program, bool(self.errors)
