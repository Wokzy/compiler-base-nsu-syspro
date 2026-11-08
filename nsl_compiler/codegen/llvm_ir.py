from nsl_compiler import libast
from dataclasses import dataclass, field

# from queue import LifoQueue


EXTENTION_ORDER = {
    "i1": 0,
    "i8": 1,
    "i16": 2,
    "i32": 3,
    "i64": 4,
}


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

    branching_nest_queue: list = field(default_factory=list)

    def reserve_id(self) -> str:
        # SSA registers must have unique ids within the function.
        ident = f"%{self.store_counter}"
        self.store_counter += 1
        return ident

    def reserve_label(self, comment: str = None) -> str:
        if comment is not None:
            ident = f"L{self.label_counter}_{comment}"
        else:
            ident = f"L{self.label_counter}"
        self.label_counter += 1
        return ident

    def post_instruction(self, inst: str) -> None:
        assert self.function is not None
        assert self.label is not None

        self.output += f"  {inst}\n"

    def switch_label(self, label: str = None) -> None:
        if label is None:
            label = self.reserve_label()

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

    def _allocate(self, type_: str = "i64", *, node: libast.ASTNode) -> str:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        ident = self.state.reserve_id()
        self.state.post_instruction(f"{ident} = alloca {type_}, align 8")
        return ident

    def _store(
        self, dst_id: str, src_id: str, type_: str = "i64", *, node: libast.ASTNode
    ) -> None:
        self._assert(type_ == "i64", node, "types not equal to int64 are not supported")

        self.state.post_instruction(f"store {type_} {src_id}, ptr {dst_id}, align 8")

    def _cast_integer(
        self,
        *,
        src_expr: EvalExprResult,
        dst_type: str,
        dst_id: str = None,
        bool_with_truncate: bool = False,
    ) -> EvalExprResult:
        """
        Lazy integer type extention/truncation with `zext` used always
        """

        assert src_expr.type_ in EXTENTION_ORDER
        assert dst_type in EXTENTION_ORDER

        if src_expr.type_ == dst_type:
            return src_expr

        if dst_type == "i1" and not bool_with_truncate:
            return self._int_to_bool(src_expr=src_expr, dst_id=dst_id)

        way = "zext"  # NOTE: better to support `sext` here
        if EXTENTION_ORDER[src_expr.type_] > EXTENTION_ORDER[dst_type]:
            way = "trunc"

        if dst_id is None:
            dst_id = self.state.reserve_id()

        self.state.post_instruction(
            f"{dst_id} = {way} {src_expr.type_} {src_expr.id_} to {dst_type}"
        )

        return EvalExprResult(
            id_=dst_id,
            type_=dst_type,
        )

    def _int_to_bool(
        self, *, src_expr: EvalExprResult, dst_id: str = None
    ) -> EvalExprResult:
        """
        Lazy convertion to bool
        """

        if src_expr.type_ == "i1":
            return EvalExprResult(
                id_=src_expr.id_,
                type_="i1",
            )

        assert (
            src_expr.type_ in EXTENTION_ORDER
        ), f"cannot convert {src_expr.type_} to bool ('i1')"

        if dst_id is None:
            dst_id = self.state.reserve_id()

        self.state.post_instruction(
            f"{dst_id} = cmp ne {src_expr.type_} {src_expr.id_}, 0"
        )

        return EvalExprResult(id_=dst_id, type_="i1")

    def _is_integer_type(self, type_: str) -> bool:
        assert type_ is not None
        return type_ in EXTENTION_ORDER

    def _castable(self, lhs_type: str, rhs_type: str) -> bool:
        if lhs_type == rhs_type:
            return True

        if lhs_type in EXTENTION_ORDER and rhs_type in EXTENTION_ORDER:
            return True

        return False

    def _mutual_cast(
        self,
        *,
        lhs_expr: EvalExprResult,
        rhs_expr: EvalExprResult,
        target_type: str = None,
    ) -> tuple[EvalExprResult, EvalExprResult]:
        """
        Takes 2 expression's results and lazily tries to cast it in following order:
            1. To target type
            2. If both are integers, cast to bigger (e.g i32, i64 -> i64, i64)
            ...
            If none succeded, throw RuntimeError

        Return order is [cast(lhs_expr), cast(rhs_expr)]
        """

        if target_type is None:
            if self._is_integer_type(lhs_expr.type_) and self._is_integer_type(
                rhs_expr.type_
            ):
                target_type = (
                    lhs_expr.type_
                    if EXTENTION_ORDER[lhs_expr.type_] > EXTENTION_ORDER[rhs_expr.type_]
                    else rhs_expr.type_
                )
            else:
                raise NotImplementedError

        if lhs_expr.type_ == target_type == rhs_expr.type_:
            return (lhs_expr, rhs_expr)

        assert self._castable(lhs_expr.type_, target_type)
        assert self._castable(rhs_expr.type_, target_type)

        return (
            self._cast_integer(
                src_expr=lhs_expr, dst_type=target_type, bool_with_truncate=False
            ),
            self._cast_integer(
                src_expr=rhs_expr, dst_type=target_type, bool_with_truncate=False
            ),
        )

    def _eval_binary_expression(
        self, node: libast.BinaryOperationExpr
    ) -> EvalExprResult:
        lhs = self._eval_expression(node.elems[0])
        rhs = self._eval_expression(node.elems[1])

        self._assert(
            self._castable(lhs.type_, rhs.type_),
            node,
            f"Type mismatch ({lhs.type_} != {rhs.type_}) and cannot be cast to each other",
        )

        store_id = self.state.reserve_id()
        return_type = None
        match node:
            case libast.BinaryArithmeticExpr():
                lhs, rhs = self._mutual_cast(lhs_expr=lhs, rhs_expr=rhs)
                self.state.post_instruction(
                    f"{store_id} = {node.subtype} {lhs.type_} {lhs.id_}, {rhs.id_}"
                )
                return_type = lhs.type_
            case libast.EqExpr() | libast.RelExpr():
                lhs, rhs = self._mutual_cast(lhs_expr=lhs, rhs_expr=rhs)
                self.state.post_instruction(
                    f"{store_id} = icmp {node.subtype} {lhs.type_} {lhs.id_}, {rhs.id_}"
                )
                return_type = "i1"
            case libast.LogicalAndExpr() | libast.LogicalOrExpr():
                lhs, rhs = self._mutual_cast(
                    lhs_expr=lhs, rhs_expr=rhs, target_type="i1"
                )

                self.state.post_instruction(
                    f"{store_id} = {node.subtype} i1 {lhs.id_}, {rhs.id_}"
                )
                return_type = "i1"
            case _:
                raise RuntimeError(f"Unknown node for binary expression parser: {node}")

        assert return_type is not None
        return EvalExprResult(
            id_=store_id,
            type_=return_type,
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
            case libast.BoolLiteral():
                return EvalExprResult(id_=str(int(node.value)), type_=node.subtype)
            case libast.Ident():
                symbol = self.state.symbols[node.value]
                if symbol.subtype == "VAR":
                    store_id = self.state.reserve_id()
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
                store_id = self.state.reserve_id()
                self.state.post_instruction(
                    f"{store_id} = sub {expr.type_} 0, {expr.id_}"
                )
                return EvalExprResult(
                    id_=store_id,
                    type_=expr.type_,
                )
            case libast.LogicalNegate():
                expr = self._eval_expression(node.elems[0])
                store_id = self.state.reserve_id()
                self.state.post_instruction(
                    f"{store_id} = icmp eq {expr.type_} {expr.id_}, {expr.type_} 0"
                )

                # NOTE: We explicitly convert logical outputs to i64 for grammar 2
                return self._cast_integer(
                    src_expr=EvalExprResult(id_=store_id, type_="i1"), dst_type="i64"
                )

        self._assert(False, node, f"Failed to eval expression {node}")

    def _declare(self, node: libast.DeclarationStatement) -> None:

        name = node.elems[0].value
        expr = self._eval_expression(node.elems[1])

        if node.subtype == "VAR":
            if expr.type_ != "i64":
                expr.id_ = self._cast_integer(src_expr=expr, dst_type="i64")
                expr.type_ = "i64"

            alloc_id = self._allocate(expr.type_, node=node)
            self._store(alloc_id, expr.id_, expr.type_, node=node)

            self.state.symbols[name] = SymbolMeta(alloc_id, expr.type_, "VAR")
            return

        # Keep the initializer operand, since val is immutable.
        self.state.symbols[name] = SymbolMeta(expr.id_, expr.type_, "VAL")

    def _generate_if_else(self, node: libast.IfStatement):
        expr_res = self._eval_expression(node.elems[0])
        expr_res = self._int_to_bool(src_expr=expr_res)

        label_if, label_finish = self.state.reserve_label(
            "if_body"
        ), self.state.reserve_label("if_else_finish")

        if len(node.elems) == 3:
            label_else = self.state.reserve_label("else_body")

            self.state.post_instruction(
                f"br i1 %{expr_res.id_}, label %{label_if}, label %{label_else}"
            )

            self.state.switch_label(label_else)
            self.generate(node.elems[2])

            self.state.post_instruction(f"br label %{label_finish}")
        else:
            self.state.post_instruction(
                f"br i1 %{expr_res.id_}, label %{label_if}, label %{label_finish}"
            )

        self.state.switch_label(label_if)
        self.generate(node.elems[1])

        self.state.switch_label(label_finish)

    def _generate_while_statement(self, node: libast.WhileStatement):
        expr_res = self._eval_expression(node.elems[0])
        expr_res = self._int_to_bool(src_expr=expr_res)

        label_condition = self.state.reserve_label("while_header")
        label_while = self.state.reserve_label("while_body")
        label_finish = self.state.reserve_label("while_finish")

        propageted_labes = (label_condition, label_finish)

        self.state.switch_label(label_condition)
        self.state.branching_nest_queue.append(propageted_labes)

        self.state.post_instruction(
            f"br i1 %{expr_res.id_}, label %{label_while}, label %{label_finish}"
        )

        self.generate(node.elems[1])

        assert (
            self.state.branching_nest_queue.pop() == propageted_labes
        ), "label inconsistency found, during while generation"

        self.state.switch_label(label_finish)

    def generate(self, node: libast.ASTNode) -> libast.ASTNode | None:

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
            case libast.WhileStatement():
                self._generate_while_statement(node)
            case libast.BreakStatement():
                self._assert(
                    len(self.state.branching_nest_queue),
                    node,
                    f"Break outside the loop",
                )

                while_finish = self.state.branching_nest_queue[-1][1]
                self.state.post_instruction(f"br label %{while_finish}")
            case libast.ContinueStatement():
                self._assert(
                    len(self.state.branching_nest_queue),
                    node,
                    f"Break outside the loop",
                )

                while_header = self.state.branching_nest_queue[-1][0]
                self.state.post_instruction(f"br label %{while_header}")
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
