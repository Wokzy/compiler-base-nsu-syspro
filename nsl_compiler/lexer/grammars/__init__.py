from .grammar_1 import Grammar1
from nsl_compiler.lexer.base import BaseGrammar

GRAMMAR_DICT = {1: Grammar1}


def get_grammar_by_id(idx: int) -> BaseGrammar:
    if idx not in GRAMMAR_DICT:
        raise ValueError(f"Specified grammar {idx} does not exist")

    return GRAMMAR_DICT[idx]


__all__ = ["Grammar1", "get_grammar_by_id"]
