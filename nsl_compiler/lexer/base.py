
from abc import ABC, abstractmethod
from .vocab import Token, Vocab


class BaseGrammar(ABC):
    vocab: Vocab

    @abstractmethod
    def _raw_tokenize(self, text: str):
        ...

    @abstractmethod
    def _postprocess(self, tokens: list[Token]):
        ...
    
    def tokenize(self, text: str, add_eof: bool = True) -> list[Token]:
        ...
