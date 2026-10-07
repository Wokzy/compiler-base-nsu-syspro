from dataclasses import dataclass, field
from typing import Any


@dataclass
class ASTNode:
    kind: str = None
    line: int = None
    column: int = None
    subtype: str = None
    value: Any = None

    elems: list["ASTNode"] = field(default_factory=list)

    def to_dict(self, elems: list = None) -> dict:
        result = {
            "kind": self.kind,
            "line": self.line,
            "column": self.column,
            "elems": (
                [node.to_dict() for node in self.elems] if elems is None else elems
            ),
        }
        if self.value is not None:
            result["value"] = self.value
        return result


@dataclass
class Program(ASTNode):
    kind: str = "Program"


@dataclass
class ReturnStatement(ASTNode):
    kind: str = "Return"

    def __post_init__(self):
        assert len(self.elems) == 1


@dataclass
class DeclarationStatement(ASTNode):
    kind: str = "Declare"

    def __post_init__(self):
        assert len(self.elems) == 2
        assert self.subtype in {"VAR", "VAL"}


@dataclass
class AssignmentStatement(ASTNode):
    kind: str = "Assign"

    def __post_init__(self):
        assert len(self.elems) == 2


@dataclass
class BinaryOperationExpr(ASTNode):
    kind: str = "BinOp"

    def __post_init__(self):
        assert len(self.elems) == 2


@dataclass
class MulExpr(BinaryOperationExpr):
    subtype: str = "MUL"


@dataclass
class SubExpr(BinaryOperationExpr):
    subtype: str = "SUB"


@dataclass
class AddExpr(BinaryOperationExpr):
    subtype: str = "ADD"


@dataclass
class DivExpr(BinaryOperationExpr):
    subtype: str = "DIV"


@dataclass
class UnaryExpression(ASTNode):
    kind: str = "Unary"

    def __post_init__(self):
        assert len(self.elems) == 1


@dataclass
class Error(ASTNode):
    kind: str = "Error"


@dataclass
class LiteralExpr(ASTNode):
    def __post_init__(self):
        assert self.value is not None


@dataclass
class IntLiteral(LiteralExpr):
    kind: str = "IntLiteral"

    def __post_init__(self):
        assert isinstance(self.value, int)


@dataclass
class Ident(LiteralExpr):
    kind: str = "Ident"

    def __post_init__(self):
        assert isinstance(self.value, str)
