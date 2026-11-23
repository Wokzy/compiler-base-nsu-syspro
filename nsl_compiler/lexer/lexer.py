from nsl_compiler.lexer import Token, Vocab


class Lexer:
    def __init__(self):
        self.vocab = Vocab(
            [
                Token("INT"),
                Token("EOF"),
                Token("IDENT"),
                Token("RETURN", "return"),
                Token("IF", "if"),
                Token("ELSE", "else"),
                Token("WHILE", "while"),
                Token("BREAK", "break"),
                Token("CONTINUE", "continue"),
                Token("TRUE", "true"),
                Token("FALSE", "false"),
                Token("VAL", "val"),
                Token("VAR", "var"),
                Token("PLUS", "+"),
                Token("MINUS", "-"),
                Token("MULT", "*"),
                Token("DIV", "/"),
                Token("ASSIGN", "="),
                Token("EQ", "=="),
                Token("NE", "!="),
                Token("LT", "<"),
                Token("GT", ">"),
                Token("LE", "<="),
                Token("GE", ">="),
                Token("AND", "&&"),
                Token("OR", "||"),
                Token("NOT", "!"),
                Token("DEF", "def"),
                Token("EXTERN", "extern"),
                Token("COMMA", ","),
                Token("LPAREN", "("),
                Token("RPAREN", ")"),
                Token("LBRACE", "{"),
                Token("RBRACE", "}"),
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

    def _postprocess(self, raw_tokens: list[list[Token]]) -> list[Token]:
        result = []
        multiline_comment_start = None

        for line in raw_tokens:
            for token in line:
                if multiline_comment_start is not None:
                    if token.kind == "COMMENT_END":
                        multiline_comment_start = None
                    continue

                if token.kind == "LINE_COMMENT":
                    break

                if token.kind == "COMMENT_BEGIN":
                    multiline_comment_start = token
                    continue

                if token.kind == "ERROR":
                    self._error(token, "Syntax Error")

                result.append(token)

        if multiline_comment_start is not None:
            error = Token(
                "ERROR",
                value="Unterminated multiline comment",
                **multiline_comment_start.location,
            )
            result.append(error)
            self._error(error, error.value)

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
