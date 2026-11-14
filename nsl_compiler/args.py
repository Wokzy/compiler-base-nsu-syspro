import argparse

from pathlib import Path
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NSLCompilerConfig:
    input_file: Path | None = None
    output_file: Path | None = None
    grammar: int = 1
    produce_ast: bool = False
    produce_llvm: bool = False
    external_command: tuple[str] = field(default_factory=tuple)

    def __post_init__(self):
        if self.external_command:
            for s in self.external_command:
                assert isinstance(s, str)


def parse_args() -> NSLCompilerConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", nargs="?", type=Path, default=None)
    parser.add_argument("output_file", nargs="?", type=Path, default=None)
    parser.add_argument("--grammar", "-g", type=int, default=1, required=False)
    parser.add_argument("--produce-ast", "-a", action="store_true", required=False)
    parser.add_argument("--produce-llvm", "-c", action="store_true", required=False)
    parser.add_argument(
        "external_command", nargs="*"
    )  # NOTE: hack for running `clang` to compile llvm

    args = parser.parse_args()
    args.external_command = tuple(args.external_command)

    return NSLCompilerConfig(**args.__dict__.copy())
