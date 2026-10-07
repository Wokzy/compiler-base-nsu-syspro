from ..lexer import Token
from . import libast


class Parser:

    def __init__(self):
        self.tokens: list[Token] = []
        self.position: int = 0
        self.errors: list[str] = []
        self.symbols: dict[str, str] = {}

    def _peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.position + offset, len(self.tokens) - 1)]

    def _advance(self, kind: str = None) -> Token:
        token = self._peek()

        if token.kind != "EOF":
            self.position += 1

        if kind is not None and token.kind != kind:
            self._error(token, f"expected {kind}, found {token.kind}")

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

        while self._peek().kind not in {"SEMI", "EOF"}:
            self._advance()

        if self._peek().kind == "SEMI":
            self._advance()

    def _parse_expression(self) -> libast.ASTNode:
        return self._parse_additive_expression()

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
            return libast.UnaryExpression(
                elems=[self._parse_unary_expression()], **operator.location
            )
        return self._parse_primary_expression()

    def _parse_primary_expression(self) -> libast.ASTNode:
        token = self._advance()
        match token.kind:
            case "INT":
                return libast.IntLiteral(value=int(token.value), **token.location)
            case "IDENT":
                if token.value not in self.symbols:
                    self._error(token, f"undeclared variable '{token.value}'")
                return libast.Ident(value=token.value, **token.location)
            case "LPAREN":
                expression = self._parse_expression()
                if self._peek().kind == "RPAREN":
                    self._advance()
                else:
                    self._error(self._peek(), "expected ')' after expression")
                return expression
            case _:
                self._error(token, f"expected expression, found {token.kind}")
                return libast.Error(**self._peek().location)

    def _parse_statement(self) -> libast.ASTNode:
        first_token = self._peek()

        match first_token.kind:
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

                self._advance("ASSIGN")
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
                self._advance()

                statement = libast.AssignmentStatement(
                    elems=[
                        libast.Ident(value=name.value, **name.location),
                        self._parse_expression(),
                    ],
                    **name.location,
                )

                if name.value not in self.symbols:
                    self._error(
                        name, f"assignment to undeclared variable '{name.value}'"
                    )
                elif self.symbols[name.value] == "VAL":
                    self._error(name, f"cannot assign to val '{name.value}'")
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
