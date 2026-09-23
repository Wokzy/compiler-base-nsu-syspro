import argparse

from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class NSLCompilerConfig:
    input_file: Path = None,
    output_file: Path = None,
    debug: bool = True

def parse_args() -> NSLCompilerConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, required=True)
    parser.add_argument("output", type=Path, default=None, required=False)
    parser.add_argument("--debug", "-g", type=bool, default=False, action="store_true",
                        help="no-op")

    return NSLCompilerConfig(**parser.parse_args().__dict__.copy())
