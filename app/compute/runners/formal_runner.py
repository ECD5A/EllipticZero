from __future__ import annotations

from functools import reduce
from typing import Any

from sympy import Integer
from sympy.parsing.sympy_parser import parse_expr

try:
    import z3
except Exception:  # pragma: no cover - optional dependency path
    z3 = None


class FormalRunner:
    """Bounded local SMT-backed formal equality checker."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        backend: str = "z3",
        timeout_seconds: int = 5,
    ) -> None:
        self.enabled = enabled
        self.backend = backend
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return self.enabled and self.backend == "z3" and z3 is not None

    def run_bounded_equality_check(
        self,
        *,
        left_expression: str,
        right_expression: str,
        variables: list[str] | None = None,
        domain_min: int = -8,
        domain_max: int = 8,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The formal bounded execution path is disabled in the current configuration.",
                notes=["Enable local_research.formal_enabled to allow bounded formal checks."],
                result_data={"backend": self.backend, "property_holds": None, "counterexample": None, "errors": []},
            )
        if not self.is_available():
            return self._result(
                status="unavailable",
                conclusion="The formal backend is not available locally, so the bounded formal path could not run.",
                notes=["Install z3-solver to enable the bounded formal equality checker."],
                result_data={"backend": self.backend, "property_holds": None, "counterexample": None, "errors": []},
            )

        try:
            left_expr = parse_expr(left_expression.replace("^", "**"), evaluate=False)
            right_expr = parse_expr(right_expression.replace("^", "**"), evaluate=False)
            inferred_variables = sorted(
                {str(symbol) for symbol in left_expr.free_symbols | right_expr.free_symbols}
            )
            active_variables = variables or inferred_variables
            if len(active_variables) > 3:
                raise ValueError("Bounded formal checks support at most 3 variables.")
            z3_symbols = {name: z3.Int(name) for name in active_variables}
            left_z3 = self._sympy_to_z3(left_expr, z3_symbols)
            right_z3 = self._sympy_to_z3(right_expr, z3_symbols)
        except Exception as exc:
            return self._result(
                status="parse_error",
                conclusion="The bounded formal checker could not translate the symbolic equality safely.",
                notes=["The formal path remained local and schema-bounded."],
                result_data={
                    "backend": self.backend,
                    "property_holds": None,
                    "counterexample": None,
                    "errors": [str(exc)],
                },
            )

        solver = z3.Solver()
        solver.set(timeout=max(1, int(self.timeout_seconds * 1000)))
        for symbol in z3_symbols.values():
            solver.add(symbol >= domain_min, symbol <= domain_max)
        solver.add(left_z3 != right_z3)
        status = solver.check()

        if status == z3.unsat:
            return self._result(
                status="ok",
                conclusion="The bounded formal checker found no counterexample in the configured local domain.",
                notes=["The equality held across the bounded SMT domain."],
                result_data={
                    "backend": self.backend,
                    "property_holds": True,
                    "counterexample": None,
                    "variables": active_variables,
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "errors": [],
                },
            )
        if status == z3.sat:
            model = solver.model()
            counterexample = {
                name: model.evaluate(symbol).as_long()
                for name, symbol in z3_symbols.items()
            }
            return self._result(
                status="observed_issue",
                conclusion="The bounded formal checker found a local counterexample.",
                notes=["The SMT solver found a satisfying bounded counterexample."],
                result_data={
                    "backend": self.backend,
                    "property_holds": False,
                    "counterexample": counterexample,
                    "variables": active_variables,
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "errors": [],
                },
            )
        return self._result(
            status="warning",
            conclusion="The bounded formal checker returned an inconclusive result.",
            notes=["The SMT solver returned unknown for the bounded equality query."],
            result_data={
                "backend": self.backend,
                "property_holds": None,
                "counterexample": None,
                "variables": active_variables,
                "domain_min": domain_min,
                "domain_max": domain_max,
                "errors": ["solver_unknown"],
            },
        )

    def _sympy_to_z3(self, expr: object, symbols: dict[str, Any]) -> Any:
        if getattr(expr, "is_Integer", False):
            return z3.IntVal(int(expr))
        if getattr(expr, "is_Symbol", False):
            name = str(expr)
            if name not in symbols:
                raise ValueError(f"Unsupported symbol outside the bounded variable set: {name}")
            return symbols[name]
        func_name = getattr(getattr(expr, "func", None), "__name__", "")
        args = list(getattr(expr, "args", ()))
        if func_name == "Add":
            return reduce(lambda left, right: left + right, [self._sympy_to_z3(arg, symbols) for arg in args])
        if func_name == "Mul":
            return reduce(lambda left, right: left * right, [self._sympy_to_z3(arg, symbols) for arg in args])
        if func_name == "Pow":
            base, exponent = args
            if not isinstance(exponent, Integer):
                raise ValueError("Only integer powers are supported by the bounded formal runner.")
            exponent_value = int(exponent)
            if exponent_value < 0 or exponent_value > 4:
                raise ValueError("Only non-negative powers up to 4 are supported by the bounded formal runner.")
            result = z3.IntVal(1)
            base_expr = self._sympy_to_z3(base, symbols)
            for _ in range(exponent_value):
                result = result * base_expr
            return result
        if func_name == "Mod":
            left, right = args
            return self._sympy_to_z3(left, symbols) % self._sympy_to_z3(right, symbols)
        raise ValueError(f"Unsupported symbolic form for bounded formal translation: {expr}")

    def _result(
        self,
        *,
        status: str,
        conclusion: str,
        notes: list[str],
        result_data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": status,
            "conclusion": conclusion,
            "notes": notes,
            "deterministic": True,
            "result_data": result_data,
        }
