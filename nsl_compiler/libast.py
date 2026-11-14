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
class Block(ASTNode):
    kind: str = "Block"


@dataclass
class IfStatement(ASTNode):
    kind: str = "If"

    def __post_init__(self):
        assert 2 <= len(self.elems) <= 3  # expr, statement, [else]


@dataclass
class WhileStatement(ASTNode):
    kind: str = "While"

    def __post_init__(self):
        assert len(self.elems) == 2


@dataclass
class BreakStatement(ASTNode):
    kind: str = "Break"

    def __post_init__(self):
        assert len(self.elems) == 0


@dataclass
class ContinueStatement(ASTNode):
    kind: str = "Continue"

    def __post_init__(self):
        assert len(self.elems) == 0


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
class BinaryArithmeticExpr(BinaryOperationExpr):
    pass


@dataclass
class MulExpr(BinaryArithmeticExpr):
    subtype: str = "mul"


@dataclass
class SubExpr(BinaryArithmeticExpr):
    subtype: str = "sub"


@dataclass
class AddExpr(BinaryArithmeticExpr):
    subtype: str = "add"


@dataclass
class DivExpr(BinaryArithmeticExpr):
    subtype: str = "sdiv"


@dataclass
class LogicalOrExpr(BinaryOperationExpr):
    subtype: str = "or"


@dataclass
class LogicalAndExpr(BinaryOperationExpr):
    subtype: str = "and"


@dataclass
class EqExpr(BinaryOperationExpr):
    subtype: str = "eq"

    def __post_init__(self):
        assert self.subtype in {"eq", "ne"}


@dataclass
class RelExpr(BinaryOperationExpr):
    subtype: str = "rel"


@dataclass
class UnaryExpression(ExpressionStatement):
    kind: str = "Unary"

    def __post_init__(self):
        assert len(self.elems) == 1


@dataclass
class UnaryMinus(UnaryExpression):
    subtype: str = "minus"

    def __post_init__(self):
        assert len(self.elems) == 1


@dataclass
class LogicalNegate(UnaryExpression):
    subtype: str = "lneg"

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
class BoolLiteral(LiteralExpr):
    kind: str = "BoolLiteral"
    subtype: str = "i1"

    def __post_init__(self):
        assert isinstance(self.value, bool)


@dataclass
class Ident(LiteralExpr):
    kind: str = "Ident"

    def __post_init__(self):
        assert isinstance(self.value, str)
