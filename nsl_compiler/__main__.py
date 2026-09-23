import sys
import json

from .args import parse_args, NSLCompilerConfig
from dataclasses import dataclass

from .lexer.grammars import get_grammar_by_id


class NSLCompiler:
    def __init__(self, config: NSLCompilerConfig):
        self.config = config
        self.grammar = get_grammar_by_id(config.grammar)()

        self.input_file = sys.stdin
        self.output_file = sys.stdout

        if self.config.input_file is not None:
            self.input_file = open(self.config.input_file, "r")
        if self.config.output_file is not None:
            self.output_file = open(self.config.output_file, "w", encoding="utf-8")

    def tokenize(self) -> bool:
        text = self.input_file.read()
        tokens, status = self.grammar.tokenize(text, add_eof=True)

        json.dump(
            [token.to_dict() for token in tokens],
            self.output_file,
            indent=2,
            ensure_ascii=False,
        )

        return status

    def compile(self) -> None:
        raise NotImplementedError


if __name__ == "__main__":
    compiler = NSLCompiler(config=parse_args())
    sys.exit(compiler.tokenize())
