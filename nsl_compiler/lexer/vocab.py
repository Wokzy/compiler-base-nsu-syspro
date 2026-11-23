from dataclasses import dataclass
from re import escape
from typing import Iterable

from tokenizers import Regex
from tokenizers.pre_tokenizers import Split


@dataclass(frozen=True)
class Token:
    kind: str = None
    value: str = None
    line: int = None
    column: int = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "line": self.line,
            "column": self.column,
        }

    @property
    def location(self):
        return {"line": self.line, "column": self.column}


class Vocab:
    def __init__(
        self,
        tokens: Iterable[Token],
        unk_token: str = "<unk>",
    ):
        self.static_tokens: dict[str, Token] = {}
        self.dynamic_tokens: set[Token] = set()
        self.unk_token = unk_token

        self.expand_from_tokens(tokens)

        symbols = [
            escape(value)
            for value in sorted(self.static_tokens, key=len, reverse=True)
            if value != unk_token and not value.isidentifier()
        ]
        pattern = "|".join(
            [r"\s+", r"[A-Za-z_][A-Za-z0-9_]*", r"[0-9]+", *symbols, r"."]
        )
        self.pre_tokenizer = Split(Regex(pattern), behavior="isolated")

    def expand_from_tokens(self, tokens: Iterable[Token]) -> None:
        for tok in tokens:
            assert tok.line is None and tok.column is None, tok
            assert tok.kind is not None, tok

            if tok.value is None:
                self.dynamic_tokens.add(tok)
            else:
                self.static_tokens[tok.value] = tok

    def expand_from_vocab(self, vocab) -> None:
        raise NotImplementedError

    def raw_tokenize(self, text: str) -> list[list[Token]]:
        token_lines = []
        for line_number, line in enumerate(text.split("\n"), start=1):
            tokens = []
            for value, (start, _) in self.pre_tokenizer.pre_tokenize_str(line):
                if value.isspace():
                    continue

                static_token = self.static_tokens.get(value)
                if static_token is not None:
                    kind = static_token.kind
                elif value.isascii() and value.isidentifier():
                    kind = "IDENT"
                elif value.isascii() and value.isdecimal():
                    kind = "INT"
                else:
                    value = self.unk_token
                    kind = self.static_tokens[value].kind

                tokens.append(Token(kind, value, line_number, start + 1))

            token_lines.append(tokens)

        return token_lines

    @property
    def size(self):
        return len(self.id_to_token)

    def __getitem__(self, key: int) -> Token:
        assert isinstance(key, int), "Token id must be integer"

        if not key in self.id_to_token:
            raise ValueError(f"No such token in vocab with id {key}")

        return self.id_to_token[key]
