from nsl_compiler.lexer import Token, Vocab
from nsl_compiler.lexer.base import BaseGrammar

from nsl_compiler.lexer import build_raw_bpe_tokens

from tokenizers import Tokenizer
from tokenizers.models import WordPiece
from tokenizers.pre_tokenizers import Whitespace


class Grammar1(BaseGrammar):
    def __init__(self):
        self.vocab = Vocab(
            [
                Token(0, "INT"),
                Token(1, "RETURN", "return"),
                Token(2, "VAL", "val"),
                Token(3, "VAR", "+"),
                Token(4, "INT", "INTEGER_LITERAL"),
                Token(5, "RETURN", "return"),
                Token(6, "VAL", "val"),
                Token(7, "VAR", "var"),
                Token(8, "PLUS", "+"),
                Token(9, "MINUS", "-"),
                Token(10, "MULT", "*"),
                Token(11, "DIV", "/"),
                Token(12, "ASSIGN", "="),
                Token(13, "LPAREN", "("),
                Token(14, "RPAREN", ")"),
                Token(15, "SEMI", ";"),
                Token(16, "EOF"),
                Token(17, "IDENT"),
                Token(18, "ERROR", "<unk>"),
                Token(19, "LINE_COMMENT", "//"),
                Token(20, "COMMENT_BEGIN", "/*"),
                Token(21, "COMMENT_END", "*/"),
            ]
        )

        self.vocab.expand_from_tokens(build_raw_bpe_tokens(self.vocab))

        self.raw_tokenizer = Tokenizer(
            WordPiece(
                vocab=self.vocab.get_raw_tokens(),
                unk_token="<unk>",
                continuing_subword_prefix="",
            )
        )
        self.raw_tokenizer.pre_tokenizer = Whitespace()

    def _raw_tokenize(self, text: str) -> list[Token]:
        lines = text.split("\n")

        result = []

        for i, line in enumerate(lines):
            if not line:
                continue

            raw = self.raw_tokenizer.encode(line)

            for token_id, offset in zip(raw.ids, raw.offsets):
                if self.vocab[token_id].kind == "LINE_COMMENT":
                    break

                result.append(
                    Token(
                        token_id,
                        kind=self.vocab[token_id].kind,
                        value=self.vocab[token_id].value,
                        line=i + 1,
                        column=offset[0] + 1,
                    )
                )

        return result

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
                        0,
                        "INT",
                        value=concat,
                        **concat_position,
                    )
                )
            elif concat[0].isalpha():
                result.append(
                    Token(
                        17,
                        "IDENT",
                        value=concat,
                        **concat_position,
                    )
                )
            else:
                raise RuntimeError(
                    f"Failed to resolve token {concat} at position {concat_position}"
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
                error = True

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
                    18,
                    "ERROR",
                    value="Unterminated multiline comment",
                    **multiline_comment_start_position,
                )
            )
            error = True

        return result, error

    def tokenize(self, text: str, add_eof: bool = True) -> tuple[list[Token], bool]:
        tokens, status = self._postprocess(self._raw_tokenize(text))

        if add_eof:
            lines = text.split("\n")
            tokens.append(
                Token(
                    id=16,
                    kind="EOF",
                    value="",
                    line=len(lines),
                    column=len(lines[-1]) + 1,
                )
            )

        return tokens, status
