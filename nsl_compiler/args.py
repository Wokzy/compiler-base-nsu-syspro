import argparse

from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class NSLCompilerConfig:
    input_file: Path | None = None
    output_file: Path | None = None
    grammar: int = 1
    produce_ast: bool = False


def parse_args() -> NSLCompilerConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", nargs="?", type=Path, default=None)
    parser.add_argument("output_file", nargs="?", type=Path, default=None)
    parser.add_argument("--grammar", "-g", type=int, default=1, required=False)
    parser.add_argument("--produce-ast", "-a", action="store_true", required=False)

    return NSLCompilerConfig(**parser.parse_args().__dict__.copy())
