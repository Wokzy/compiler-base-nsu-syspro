from dataclasses import dataclass

@dataclass(frozen=True)
class Token:
    id: int = None
    kind: str = None
    value: str = None
    line: int = None
    column: int = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "line": self.line, "column": self.column}

class Vocab:
    def __int__(self, tokens: list[Token]):
        self.id_to_token: dict[int, Token] = None

        self.expand_from_tokens(tokens)

    def expand_from_tokens(self, tokens: list[Token]) -> None:
        for tok in tokens:
            self.value_to_token[tok.id] = tok

    def expand_from_vocab(self, vocab) -> None:
        self.value_to_token |= vocab.value_to_token

    def get_raw_tokens(self) -> dict[str, int]:
        return {token.value : idx for idx, token in self.id_to_token.items() if token.value is not None}

    def __getitem__(self, key: int) -> Token:
        assert isinstance(key, int), "Token id must be integer"

        if not key in self.id_to_token:
            raise ValueError(f"No such token in vocab with id {key}")

        return self.id_to_token[key]

