from nsl_compiler.lexer import Token, Vocab


from enum import Enum


class Lexer:
    def __init__(self):
        self.vocab = Vocab(
            [
                Token("INT"),
                Token("EOF"),
                Token("IDENT"),
                Token("RETURN", "return"),
                Token("VAL", "val"),
                Token("VAR", "var"),
                Token("PLUS", "+"),
                Token("MINUS", "-"),
                Token("MULT", "*"),
                Token("DIV", "/"),
                Token("ASSIGN", "="),
                Token("LPAREN", "("),
                Token("RPAREN", ")"),
                Token("SEMI", ";"),
                Token("ERROR", "<unk>"),
                Token("LINE_COMMENT", "//"),
                Token("COMMENT_BEGIN", "/*"),
                Token("COMMENT_END", "*/"),
            ]
        )

        self.errors: list[str] = []

    def _error(self, token: Token, message: str) -> None:
        self.errors.append(
            f"Error: line {token.line}, column {token.column}: {message}"
        )

    def _postprocess(self, raw_tokens: list[Token]) -> tuple[list[Token], bool]:

        result = []
        concat: str = ""
        concat_position = {"line": 0, "column": 0}

        error = False

        def __resolve_concat():
            nonlocal result, concat, concat_position

            if concat.isnumeric():
                result.append(
                    Token(
                        "INT",
                        value=concat,
                        **concat_position,
                    )
                )
            elif concat[0].isalpha():
                result.append(
                    Token(
                        "IDENT",
                        value=concat,
                        **concat_position,
                    )
                )
            else:
                self._error(
                    Token(
                        "ERROR",
                        **multiline_comment_start_position,
                    ),
                    f"Failed to resolve token {concat}"
                )

            concat = ""
            concat_position = {"line": 0, "column": 0}

        multiline_comment = False
        multiline_comment_start_position = {"line": 0, "column": 0}

        for token in raw_tokens:
            if token.kind == "COMMENT_BEGIN":
                multiline_comment = True
                multiline_comment_start_position["line"] = token.line
                multiline_comment_start_position["column"] = token.column
                continue

            if multiline_comment:
                if token.kind == "COMMENT_END":
                    multiline_comment = False
                    multiline_comment_start_position = {"line": 0, "column": 0}
                continue

            if token.kind == "ERROR":
                self._error(token, "Syntax Error")

            if token.kind != "RAW_BPE":
                if concat:
                    __resolve_concat()

                result.append(token)
            else:
                if not concat:
                    concat_position["line"] = token.line
                    concat_position["column"] = token.column

                assert len(token.value) == 1
                concat += token.value

        if concat:
            __resolve_concat()

        if multiline_comment:
            result.append(
                Token(
                    "ERROR",
                    value="Unterminated multiline comment",
                    **multiline_comment_start_position,
                )
            )

            self._error(result[-1], result[-1].value)

        return result

    def tokenize(self, text: str, add_eof: bool = True) -> tuple[list[Token], bool]:
        self.errors = []

        tokens = self._postprocess(self.vocab.raw_tokenize(text))

        if add_eof:
            lines = text.split("\n")
            tokens.append(
                Token(
                    kind="EOF",
                    line=len(lines),
                    column=len(lines[-1]) + 1,
                )
            )

        return tokens, bool(self.errors)
