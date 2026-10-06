from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from tokenizers import Tokenizer
from tokenizers.models import WordPiece
from tokenizers.pre_tokenizers import Whitespace


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


class Vocab:
    def __init__(
        self,
        tokens: Iterable[Token],
        include_bpe: bool = True,
        raw_bpe_kind: str = "RAW_BPE",
        unk_token: str = "<unk>",
    ):
        self.static_tokens: dict[str, Token] = {}
        self.dynamic_tokens: set[Token] = set()

        self.expand_from_tokens(tokens)

        if include_bpe:
            self.expand_from_tokens(build_alnum_tokens(raw_bpe_kind))

        self.static_tokenizer = Tokenizer(
            WordPiece(
                vocab={
                    token.value: idx
                    for idx, token in enumerate(self.static_tokens.values())
                },
                unk_token=unk_token,
                continuing_subword_prefix="",
            )
        )
        self.static_tokenizer.pre_tokenizer = Whitespace()

    def expand_from_tokens(self, tokens: list[Token]) -> None:
        for tok in tokens:
            assert tok.line is None and tok.column is None, tok
            assert tok.kind is not None, tok

            if tok.value is None:
                self.dynamic_tokens.add(tok)
            else:
                self.static_tokens[tok.value] = tok

    def expand_from_vocab(self, vocab) -> None:
        raise NotImplementedError

    def raw_tokenize(self, text: str) -> list[Token]:
        lines = text.split("\n")

        result = []

        for i, line in enumerate(lines):
            if not line:
                continue

            raw = self.static_tokenizer.encode(line)

            for value, offset in zip(raw.tokens, raw.offsets):
                result.append(
                    Token(
                        kind=self.static_tokens[value].kind,
                        value=value,
                        line=i + 1,
                        column=offset[0] + 1,
                    )
                )

        return result

    @property
    def size(self):
        return len(self.id_to_token)

    def __getitem__(self, key: int) -> Token:
        assert isinstance(key, int), "Token id must be integer"

        if not key in self.id_to_token:
            raise ValueError(f"No such token in vocab with id {key}")

        return self.id_to_token[key]


def build_alnum_tokens(raw_bpe_kind: str) -> list[Token]:

    res = []

    alpahnum = "qwertyuiopasdfghjklzxcvbnm"
    alpahnum += alpahnum.upper()
    alpahnum += "0123456789"

    for c in alpahnum:
        res.append(
            Token(
                kind=raw_bpe_kind,
                value=c,
            )
        )

    return res

