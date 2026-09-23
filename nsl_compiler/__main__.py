import json

from .args import parse_args, NSLCompilerConfig
from dataclasses import dataclass

class NSLCompiler:
    def __init__(self, config: NSLCompilerConfig):
        self.config = config
        self.tokenizer = None

    def tokenize(self) -> dict:
        pass

    def compile(self) -> None:
        raise NotImplementedError


if __name__ == "__main__":
    compiler = NSLCompilerConfig(config=parse_args())
    compiler.tokenize()

