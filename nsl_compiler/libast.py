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

    def __iter__(self):
        for elem in self.elems:
            yield elem


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
class ExpressionStatement(ASTNode):
    kind: str = "Expression"


@dataclass
class BinaryOperationExpr(ExpressionStatement):
    kind: str = "BinOp"

    def __post_init__(self):
        assert len(self.elems) == 2


@dataclass
class MulExpr(BinaryOperationExpr):
    subtype: str = "mul"


@dataclass
class SubExpr(BinaryOperationExpr):
    subtype: str = "sub"


@dataclass
class AddExpr(BinaryOperationExpr):
    subtype: str = "add"


@dataclass
class DivExpr(BinaryOperationExpr):
    subtype: str = "sdiv"


@dataclass
class UnaryExpression(ExpressionStatement):
    kind: str = "Unary"

    def __post_init__(self):
        assert len(self.elems) == 1


@dataclass
class Error(ASTNode):
    kind: str = "Error"


@dataclass
class LiteralExpr(ExpressionStatement):
    def __post_init__(self):
        assert self.value is not None
        assert self.subtype is not None


@dataclass
class IntLiteral(LiteralExpr):
    kind: str = "IntLiteral"
    subtype: str = "i64"

    def __post_init__(self):
        assert isinstance(self.value, int)


@dataclass
class Ident(LiteralExpr):
    kind: str = "Ident"

    def __post_init__(self):
        assert isinstance(self.value, str)
