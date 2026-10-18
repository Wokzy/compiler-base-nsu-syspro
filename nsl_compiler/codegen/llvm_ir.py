from nsl_compiler import libast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolMeta:
    id_: str
    type_: str
    subtype: str | None

    @property
    def assinable(self):
        return self.subtype == "VAR"


@dataclass()
class EvalExprResult:
    id_: str
    code: list[str] = field(default_factory=list)
    type_: str = "i64"


class Visitor:
    def __init__(self):
        self.store_counter: int = 0
        self.symbols: dict[str, SymbolMeta] = {}

    def _assert(self, cond: bool, node: libast.ASTNode, message: str) -> None:
        if not cond:
            raise RuntimeError(
                f"Error: line {node.line}, column {node.column}: {message}"
            )

    def __reserve_id(self) -> str:
        # SSA registers must have unique ids within the function.
        self.store_counter += 1
        return f"%{self.store_counter}"

    def _concat_instructions(self, inst: list[str], indent=2) -> str:
        return "\n".join(map(lambda x: " " * indent + x, inst))

    def _allocate(
        self, type_: str = "i64", *, node: libast.ASTNode
    ) -> tuple[str, list[str]]:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        ident = self.__reserve_id()
        return ident, [f"{ident} = alloca i64, align 8"]

    def _store(
        self, dst_id: str, src_id: str, type_: str = "i64", *, node: libast.ASTNode
    ) -> list[str]:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        return [f"store i64 {src_id}, ptr {dst_id}, align 8"]

    def _eval_binary_expression(
        self, node: libast.BinaryOperationExpr
    ) -> EvalExprResult:
        lhs = self._eval_expression(node.elems[0])
        rhs = self._eval_expression(node.elems[1])

        self._assert(
            lhs.type_ == rhs.type_, node, f"Type mismatch ({lhs.type_} != {rhs.type_})"
        )

        store_id = self.__reserve_id()
        return EvalExprResult(
            code=(
                lhs.code
                + rhs.code
                + [f"{store_id} = {node.subtype} {lhs.type_} {lhs.id_}, {rhs.id_}"]
            ),
            id_=store_id,
            type_=lhs.type_,
        )

    def _eval_expression(self, node: libast.ExpressionStatement) -> EvalExprResult:
        match node:
            case libast.BinaryOperationExpr():
                return self._eval_binary_expression(node)
            case libast.IntLiteral():
                return EvalExprResult(
                    id_=str(node.value),
                    type_=node.subtype,
                )
            case libast.Ident():
                symbol = self.symbols[node.value]
                if symbol.subtype == "VAR":
                    store_id = self.__reserve_id()
                    return EvalExprResult(
                        code=[
                            f"{store_id} = load {symbol.type_}, ptr {symbol.id_}, align 8"
                        ],
                        id_=store_id,
                    )
                return EvalExprResult(id_=symbol.id_)
            case libast.UnaryExpression():
                store_id = self.__reserve_id()
                expr = self._eval_expression(node.elems[0])
                return EvalExprResult(
                    code=expr.code
                    + [f"{store_id} = sub {expr.type_}, {expr.type_} 0, {expr.id_}"],
                    id_=store_id,
                    type_=expr.type_,
                )

        self._assert(False, node, f"Failed to eval expression {node}")

    def _declare(self, node: libast.DeclarationStatement) -> list[str]:

        name = node.elems[0].value
        expr = self._eval_expression(node.elems[1])

        if node.subtype == "VAR":
            alloc_id, alloc_code = self._allocate(expr.type_, node=node)
            store_code = self._store(alloc_id, expr.id_, expr.type_, node=node)

            self.symbols[name] = SymbolMeta(alloc_id, expr.type_, "VAR")
            return expr.code + alloc_code + store_code

        # Keep the initializer operand, since val is immutable.
        self.symbols[name] = SymbolMeta(expr.id_, expr.type_, "VAL")
        return expr.code

    def generate(self, node: libast.ASTNode) -> list[str]:

        match node:
            case libast.Program():
                code, _ = self.generate_program(node)
                return [code]
            case libast.DeclarationStatement():
                return self._declare(node)
            case libast.ExpressionStatement():
                return self._eval_expression(node).code
            case libast.AssignmentStatement():
                expr = self._eval_expression(node.elems[1])
                symbol = self.symbols[node.elems[0].value]

                self._assert(
                    expr.type_ == symbol.type_,
                    node,
                    f"Type mismatch ({expr.type_} != {symbol.type_})",
                )
                self._assert(symbol.assinable, node, "Cannot assign to val")

                return expr.code + self._store(
                    symbol.id_, expr.id_, type_=expr.type_, node=node
                )
            case _:
                self._assert(False, node, f"Undefined statement {node}")

    def generate_program(self, program: libast.Program) -> str:

        self.store_counter = 0
        self.symbols.clear()

        # NOTE: for grammar1 program is impicit main fuction,
        # so we explicitly put all instructions in @main

        res = []
        ret_type = None

        for node in program:
            if isinstance(node, libast.ReturnStatement):
                expr = self._eval_expression(node.elems[0])
                self._assert(
                    expr.type_ in ["i32", "i64"],
                    node,
                    f"Unsupported return type {expr.type_}",
                )

                res.extend(expr.code + [f"ret {expr.type_} {expr.id_}"])
                ret_type = expr.type_
                break

            res.extend(self.generate(node))

        self._assert(
            ret_type is not None, program, "Program must contain a return statement"
        )

        return f"""
define {ret_type} @main() {{
{self._concat_instructions(res)}
}}\n
"""
