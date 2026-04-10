from __future__ import annotations

from typing import Any

from sympy import SympifyError, simplify
from sympy.parsing.sympy_parser import parse_expr


class SympyRunner:
    """Bounded local SymPy runner for deterministic symbolic checks."""

    def __init__(self, *, enabled: bool = True, max_expression_length: int = 512) -> None:
        self.enabled = enabled
        self.max_expression_length = max_expression_length

    def is_available(self) -> bool:
        return self.enabled

    def run_symbolic(
        self,
        *,
        expression: str,
        comparison_expression: str | None = None,
    ) -> dict[str, Any]:
        normalized = expression.strip()
        comparison = comparison_expression.strip() if comparison_expression else None
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="SymPy-backed symbolic execution is disabled in the current configuration.",
                notes=["Enable local_research.sympy_enabled to allow bounded SymPy execution."],
                result_data={
                    "backend": "sympy_runner",
                    "parsed": False,
                    "normalized_form": None,
                    "comparison_normalized_form": None,
                    "equivalent": None,
                    "errors": [],
                },
            )
        if not normalized:
            return self._result(
                status="invalid_input",
                conclusion="No symbolic expression was available for bounded SymPy execution.",
                notes=["expression cannot be empty."],
                result_data={
                    "backend": "sympy_runner",
                    "parsed": False,
                    "normalized_form": None,
                    "comparison_normalized_form": None,
                    "equivalent": None,
                    "errors": ["empty_expression"],
                },
            )
        if len(normalized) > self.max_expression_length or (
            comparison is not None and len(comparison) > self.max_expression_length
        ):
            return self._result(
                status="invalid_input",
                conclusion="The symbolic input exceeds the bounded SymPy input size.",
                notes=[f"Each symbolic expression must remain <= {self.max_expression_length} characters."],
                result_data={
                    "backend": "sympy_runner",
                    "parsed": False,
                    "normalized_form": None,
                    "comparison_normalized_form": None,
                    "equivalent": None,
                    "errors": ["expression_too_large"],
                },
            )

        try:
            left_expr = parse_expr(normalized.replace("^", "**"), evaluate=False)
            left_normalized = str(simplify(left_expr))
            if comparison is None:
                return self._result(
                    status="ok",
                    conclusion="SymPy normalized the symbolic expression locally.",
                    notes=["The symbolic path remained bounded and deterministic."],
                    result_data={
                        "backend": "sympy_runner",
                        "parsed": True,
                        "normalized_form": left_normalized,
                        "comparison_normalized_form": None,
                        "equivalent": None,
                        "errors": [],
                    },
                )

            right_expr = parse_expr(comparison.replace("^", "**"), evaluate=False)
            right_normalized = str(simplify(right_expr))
            equivalent = bool(simplify(left_expr - right_expr) == 0)
            return self._result(
                status="ok" if equivalent else "observed_issue",
                conclusion=(
                    "SymPy found the bounded symbolic forms equivalent."
                    if equivalent
                    else "SymPy found the bounded symbolic forms non-equivalent."
                ),
                notes=["The symbolic equivalence check remained bounded and deterministic."],
                result_data={
                    "backend": "sympy_runner",
                    "parsed": True,
                    "normalized_form": left_normalized,
                    "comparison_normalized_form": right_normalized,
                    "equivalent": equivalent,
                    "errors": [],
                },
            )
        except (SympifyError, TypeError, ValueError, SyntaxError) as exc:
            return self._result(
                status="parse_error",
                conclusion="SymPy could not parse the bounded symbolic input safely.",
                notes=["SymPy parsing failed under the local bounded symbolic runner."],
                result_data={
                    "backend": "sympy_runner",
                    "parsed": False,
                    "normalized_form": None,
                    "comparison_normalized_form": None,
                    "equivalent": None,
                    "errors": [str(exc)],
                },
            )

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
