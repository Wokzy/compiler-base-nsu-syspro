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
    type_: str = "i64"


@dataclass(frozen=False)
class VisitorState:
    store_counter: int = 0
    label_counter: int = 0
    symbols: dict[str, SymbolMeta] = field(default_factory=dict)

    labels: set[str] = field(default_factory=set)

    function: str = None
    label: str = None
    output: str = ""

    def post_instruction(self, inst: str) -> None:
        assert self.function is not None
        assert self.label is not None

        self.output += f"  {inst}\n"

    def switch_label(self, label: str = None) -> None:
        if label is None:
            label = f"L{self.label_counter}"
            self.label_counter += 1

        if label == self.label:
            return

        assert self.function is not None
        assert label not in self.labels

        self.output += f"\n{label}:\n"
        self.label = label
        self.labels.add(label)

    def switch_function(self, name: str, ret_type: str) -> None:
        if name == self.function:
            return

        functions = {
            name: symbol
            for name, symbol in self.symbols.items()
            if symbol.type_ == "function"
        }
        assert name not in functions

        if self.function is not None:
            self.output += "}\n\n"
        self.output += f"define {ret_type} @{name}() {{\nentry:\n"

        self.function = name
        self.label = "entry"
        self.store_counter = 0
        self.label_counter = 0
        self.labels = {"entry"}
        self.symbols = functions
        self.symbols[name] = SymbolMeta(
            id_=name,
            type_="function",
            subtype=ret_type,
        )


class Visitor:
    def __init__(self):
        self.state: VisitorState = None

    def _assert(self, cond: bool, node: libast.ASTNode, message: str) -> None:
        if not cond:
            raise RuntimeError(
                f"Error: line {node.line}, column {node.column}: {message}"
            )

    def __reserve_id(self) -> str:
        # SSA registers must have unique ids within the function.
        ident = f"%{self.state.store_counter}"
        self.state.store_counter += 1
        return ident

    def _allocate(self, type_: str = "i64", *, node: libast.ASTNode) -> str:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        ident = self.__reserve_id()
        self.state.post_instruction(f"{ident} = alloca i64, align 8")
        return ident

    def _store(
        self, dst_id: str, src_id: str, type_: str = "i64", *, node: libast.ASTNode
    ) -> None:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        self.state.post_instruction(f"store i64 {src_id}, ptr {dst_id}, align 8")

    def _eval_binary_expression(
        self, node: libast.BinaryOperationExpr
    ) -> EvalExprResult:
        lhs = self._eval_expression(node.elems[0])
        rhs = self._eval_expression(node.elems[1])

        self._assert(
            lhs.type_ == rhs.type_, node, f"Type mismatch ({lhs.type_} != {rhs.type_})"
        )

        store_id = self.__reserve_id()
        self.state.post_instruction(
            f"{store_id} = {node.subtype} {lhs.type_} {lhs.id_}, {rhs.id_}"
        )
        return EvalExprResult(
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
                symbol = self.state.symbols[node.value]
                if symbol.subtype == "VAR":
                    store_id = self.__reserve_id()
                    self.state.post_instruction(
                        f"{store_id} = load {symbol.type_}, ptr {symbol.id_}, align 8"
                    )
                    return EvalExprResult(
                        id_=store_id,
                        type_=symbol.type_,
                    )
                return EvalExprResult(id_=symbol.id_, type_=symbol.type_)
            case libast.UnaryMinus():
                expr = self._eval_expression(node.elems[0])
                store_id = self.__reserve_id()
                self.state.post_instruction(
                    f"{store_id} = sub {expr.type_} 0, {expr.id_}"
                )
                return EvalExprResult(
                    id_=store_id,
                    type_=expr.type_,
                )

        self._assert(False, node, f"Failed to eval expression {node}")

    def _declare(self, node: libast.DeclarationStatement) -> None:

        name = node.elems[0].value
        expr = self._eval_expression(node.elems[1])

        if node.subtype == "VAR":
            alloc_id = self._allocate(expr.type_, node=node)
            self._store(alloc_id, expr.id_, expr.type_, node=node)

            self.state.symbols[name] = SymbolMeta(alloc_id, expr.type_, "VAR")
            return

        # Keep the initializer operand, since val is immutable.
        self.state.symbols[name] = SymbolMeta(expr.id_, expr.type_, "VAL")

    def generate(self, node: libast.ASTNode) -> None:

        match node:
            case libast.Program():
                self.generate_program(node)
            case libast.Block():
                for inner in node.elems:
                    self.generate(inner)
            case libast.DeclarationStatement():
                self._declare(node)
            case libast.ExpressionStatement():
                self._eval_expression(node)
            case libast.ReturnStatement():
                expr = self._eval_expression(node.elems[0])
                self._assert(
                    expr.type_ in ["i32", "i64"],
                    node,
                    f"Unsupported return type {expr.type_}",
                )
                self.state.post_instruction(f"ret {expr.type_} {expr.id_}")
            case libast.AssignmentStatement():
                expr = self._eval_expression(node.elems[1])
                symbol = self.state.symbols[node.elems[0].value]

                self._assert(
                    expr.type_ == symbol.type_,
                    node,
                    f"Type mismatch ({expr.type_} != {symbol.type_})",
                )
                self._assert(symbol.assinable, node, "Cannot assign to val")

                self._store(symbol.id_, expr.id_, type_=expr.type_, node=node)
            case libast.IfStatement():
                self._generate_if_else(node)
            case _:
                self._assert(False, node, f"Undefined statement {node}")

    def generate_program(
        self, program: libast.Program, *, state: VisitorState = None
    ) -> str:
        """Emit into an active supplied state, or build a complete main function."""

        if state is None:
            self.state = VisitorState()
            self.state.switch_function("main", "i64")
        else:
            self.state = state

        has_return = False

        for node in program:
            self.generate(node)
            if isinstance(node, libast.ReturnStatement):
                has_return = True
                break

        self._assert(has_return, program, "Program must contain a return statement")

        # A supplied state leaves function wrapping to its caller.
        if state is None:
            self.state.output += "}\n"
            self.state.function = None
            self.state.label = None

        return self.state.output
