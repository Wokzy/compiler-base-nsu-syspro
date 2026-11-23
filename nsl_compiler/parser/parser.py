from ..lexer import Token
from nsl_compiler import libast

TOP_DECLARATION_KEYWORDS = {"DEF", "EXTERN"}


class Parser:

    def __init__(self):
        self.tokens: list[Token] = []
        self.position: int = 0
        self.errors: list[str] = []

        self.top_level_symbols: set[str] = set()
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

    def declared(self, token: Token) -> bool:
        return token.value in self.top_level_symbols or token.value in self.symbols

    def _finish_statement(self, force: bool = False) -> None:
        if self._peek().kind == "SEMI":
            self._advance()
            return

        if not force:
            self._error(self._peek(), "expected ';' after statement")

        boundaries = TOP_DECLARATION_KEYWORDS | {"SEMI", "RBRACE", "EOF"}
        while self._peek().kind not in boundaries:
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
                subtype="s"  # NOTE: we have no types in grammar3, so we use 's' prefix here
                + operator.kind.lower(),
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

        return self._parse_call_expression()

    def _parse_call_expression(self) -> libast.ASTNode:
        callee = self._parse_primary_expression()

        if self._peek().kind == "LPAREN":
            opening = self._advance()

            elems = [callee]
            if self._peek().kind != "RPAREN":
                while True:
                    elems.append(self._parse_expression())
                    if self._peek().kind != "COMMA":
                        break
                    self._advance()

            if self._advance("RPAREN").kind != "RPAREN":
                return libast.Error(**opening.location)

            if not isinstance(callee, libast.Ident):
                self._error(opening, "expected a function name before '('")
                return libast.Error(**opening.location)

            if callee.value in self.symbols:
                self._error(opening, f"cannot call variable '{callee.value}'")

            callee = libast.Call(elems=elems, **opening.location)

        return callee

    def _parse_primary_expression(self) -> libast.ASTNode:
        next_token = self._peek()

        if next_token.kind in TOP_DECLARATION_KEYWORDS | {
            "COMMA",
            "RPAREN",
            "SEMI",
            "RBRACE",
        }:
            self._error(next_token, f"expected expression, found {next_token.kind}")
            return libast.Error(**next_token.location)

        token = self._advance()
        match token.kind:
            case "INT":
                return libast.IntLiteral(value=int(token.value), **token.location)
            case "TRUE" | "FALSE":
                return libast.BoolLiteral(value=token.kind == "TRUE", **token.location)
            case "IDENT":
                if not self.declared(token):
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
                boundaries = TOP_DECLARATION_KEYWORDS | {"RBRACE", "EOF"}
                while self._peek().kind not in boundaries:
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

                if self.declared(name):
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

                if not self.declared(name):
                    self._error(
                        name, f"assignment to undeclared variable '{name.value}'"
                    )
                elif name.value in self.top_level_symbols:
                    self._error(name, f"cannot assign to function '{name.value}'")
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

    def _parse_function(self, first_token: Token) -> libast.ASTNode:
        if first_token.kind == "EXTERN" and self._advance("DEF").kind != "DEF":
            return libast.Error(**first_token.location)

        func_name = self._advance("IDENT")
        if func_name.kind != "IDENT" or self._advance("LPAREN").kind != "LPAREN":
            return libast.Error(**first_token.location)

        self.symbols = {}

        func_elems = [
            libast.Ident(
                subtype="function",
                value=func_name.value,
                **func_name.location,
            )
        ]

        if self._peek().kind != "RPAREN":
            while True:
                name = self._advance("IDENT")

                if name.kind != "IDENT":
                    return libast.Error(**first_token.location)

                if name.value in self.symbols:
                    self._error(name, f"parameter '{name.value}' is already declared")

                self.symbols[name.value] = (
                    "VAL"  # NOTE: Here we explicitly disallow parameter modification
                )

                func_elems.append(
                    libast.Ident(subtype="i64", value=name.value, **name.location)
                )

                if self._peek().kind != "COMMA":
                    break

                self._advance()

        if self._advance("RPAREN").kind != "RPAREN":
            return libast.Error(**first_token.location)

        if first_token.kind == "EXTERN":
            if self._advance("SEMI").kind != "SEMI":
                return libast.Error(**first_token.location)

            return libast.ExternDecl(elems=func_elems, **first_token.location)

        opening = self._peek()

        if opening.kind != "LBRACE":
            self._error(opening, "expected function body")
            return libast.Error(**first_token.location)

        body = self._parse_statement()
        func_elems.append(body)

        exits = self._statement_exits(body)
        if "fallthrough" in exits or "return" not in exits:
            self._error(
                func_name, f"function '{func_name.value}' does not return on every path"
            )

        return libast.FuncDecl(elems=func_elems, **first_token.location)

    def parse_top_declaration(self) -> libast.ASTNode:
        first_token = self._advance()

        if first_token.kind in TOP_DECLARATION_KEYWORDS:
            return self._parse_function(first_token)

        self._error(first_token, "expected a top-level function declaration")
        return libast.Error(**first_token.location)

    def _collect_function_names(self) -> set[str]:
        names = set()
        brace_depth = 0

        for token, next_token in zip(self.tokens, self.tokens[1:]):
            if token.kind == "LBRACE":
                brace_depth += 1
            elif token.kind == "RBRACE":
                brace_depth = max(0, brace_depth - 1)
            elif (
                brace_depth == 0 and token.kind == "DEF" and next_token.kind == "IDENT"
            ):
                names.add(next_token.value)

        return names

    def _statement_exits(self, statement: libast.ASTNode) -> set[str]:
        """
        We need this lookup to find out, does function body have a return statement on every reachable path.
        Example gracia:

        def foo(a) {
            if (a > 5)
                return 1;
            else
                return 0;
        }

        in this case last Block element of foo won't be a return statement
        but foo always returns a value
        """

        match statement:
            case libast.ReturnStatement():
                return {"return"}
            case libast.BreakStatement():
                return {"break"}
            case libast.ContinueStatement():
                return {"continue"}
            case libast.Block(elems=statements):
                exits = {"fallthrough"}

                for child in statements:
                    if "fallthrough" not in exits:
                        break

                    exits.remove("fallthrough")
                    exits.update(self._statement_exits(child))

                return exits
            case libast.IfStatement(elems=[condition, then_branch, *else_branch]):
                truth = libast._literal_to_bool(
                    condition
                )  # NOTE: used to ignore unreachable paths
                exits = set()

                if truth is not False:
                    exits.update(self._statement_exits(then_branch))

                if truth is not True:
                    exits.update(
                        self._statement_exits(else_branch[0])
                        if else_branch
                        else {"fallthrough"}
                    )

                return exits

            case libast.WhileStatement(elems=[condition, loop_body]):
                truth = libast._literal_to_bool(
                    condition
                )  # NOTE: used to ignore unreachable paths
                if truth is False:
                    return {"fallthrough"}

                body_exits = self._statement_exits(loop_body)
                exits = body_exits & {"return"}

                if truth is not True or "break" in body_exits:
                    exits.add("fallthrough")

                return exits
            case _:
                return {"fallthrough"}

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

        self.top_level_symbols = self._collect_function_names()
        program = libast.Program(**self._peek().location)

        while self._peek().kind != "EOF":
            declaration = self.parse_top_declaration()
            program.elems.append(declaration)

            if isinstance(declaration, libast.Error):
                while self._peek().kind not in TOP_DECLARATION_KEYWORDS | {"EOF"}:
                    self._advance()

        if (
            len(
                [
                    True
                    for node in program.elems
                    if isinstance(node, libast.FuncDecl)
                    and node.elems[0].value == "main"
                ]
            )
            != 1
        ):
            self._error(self._peek(), "expected only 1 definition of 'main'")

        return program, bool(self.errors)
