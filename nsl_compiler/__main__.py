import sys
import json

from .args import parse_args, NSLCompilerConfig
from dataclasses import dataclass

from .lexer import Lexer
from .parser import Parser


class NSLCompiler:
    def __init__(self, config: NSLCompilerConfig):
        self.config = config
        self.lexer = Lexer()
        self.parser = Parser()

        self.input_file = sys.stdin
        self.output_file = sys.stdout

        if self.config.input_file is not None:
            self.input_file = open(self.config.input_file, "r")
        if self.config.output_file is not None:
            self.output_file = open(self.config.output_file, "w", encoding="utf-8")

    def tokenize(self) -> bool:
        text = self.input_file.read()
        tokens, status = self.lexer.tokenize(text, add_eof=True)

        json.dump(
            [token.to_dict() for token in tokens],
            self.output_file,
            indent=2,
            ensure_ascii=False,
        )

        self.print_errors()
        return status

    def produce_ast(self) -> bool:
        tokens, lexer_error = self.lexer.tokenize(self.input_file.read(), add_eof=True)
        program, parser_error = self.parser.parse(tokens)

        json.dump(program.to_dict(), self.output_file, indent=2, ensure_ascii=False)

        self.print_errors()
        return lexer_error or parser_error

    def print_errors(self) -> None:
        for error in self.lexer.errors + self.parser.errors:
            print(error, file=sys.stderr)

    def compile(self) -> None:
        raise NotImplementedError


if __name__ == "__main__":
    config = parse_args()
    compiler = NSLCompiler(config=config)

    if config.produce_ast:
        sys.exit(compiler.produce_ast())
    sys.exit(compiler.tokenize())
