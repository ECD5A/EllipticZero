from __future__ import annotations

from typing import Any

from sympy import lambdify
from sympy.parsing.sympy_parser import parse_expr

try:
    from hypothesis import Phase, find, settings
    from hypothesis import strategies as st
    from hypothesis.errors import NoSuchExample
except Exception:  # pragma: no cover - optional dependency path
    Phase = None
    NoSuchExample = None
    find = None
    settings = None
    st = None


class PropertyRunner:
    """Bounded local property-based search using Hypothesis when available."""

    def __init__(self, *, enabled: bool = True, max_examples: int = 24) -> None:
        self.enabled = enabled
        self.max_examples = max_examples

    def is_available(self) -> bool:
        return self.enabled and all(
            dependency is not None
            for dependency in (Phase, NoSuchExample, find, settings, st)
        )

    def run_equality_property(
        self,
        *,
        left_expression: str,
        right_expression: str,
        variables: list[str] | None = None,
        domain_min: int = -8,
        domain_max: int = 8,
        max_examples: int | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="Property-based execution is disabled in the current configuration.",
                notes=["Enable local_research.property_enabled to allow bounded property searches."],
                result_data={"backend": "hypothesis", "property_holds": None, "counterexample": None, "errors": []},
            )
        if not self.is_available():
            return self._result(
                status="unavailable",
                conclusion="Hypothesis is not available locally, so the bounded property-based path could not run.",
                notes=["Install the research dependencies to enable property-based local checks."],
                result_data={"backend": "hypothesis", "property_holds": None, "counterexample": None, "errors": []},
            )

        sample_budget = max(1, min(max_examples or self.max_examples, self.max_examples))
        try:
            left_expr = parse_expr(left_expression.replace("^", "**"), evaluate=False)
            right_expr = parse_expr(right_expression.replace("^", "**"), evaluate=False)
            inferred_variables = sorted(
                {str(symbol) for symbol in left_expr.free_symbols | right_expr.free_symbols}
            )
            active_variables = variables or inferred_variables
            if len(active_variables) > 3:
                raise ValueError("Bounded property search supports at most 3 variables.")
            unknown_variables = set(active_variables) - set(inferred_variables)
            if unknown_variables:
                raise ValueError(f"Variables are not present in the parsed expressions: {sorted(unknown_variables)}")
            left_fn = lambdify(active_variables, left_expr, modules="math")
            right_fn = lambdify(active_variables, right_expr, modules="math")
        except Exception as exc:
            return self._result(
                status="parse_error",
                conclusion="The bounded property search could not parse the symbolic equality safely.",
                notes=["Property-based execution remained local and bounded."],
                result_data={
                    "backend": "hypothesis",
                    "property_holds": None,
                    "counterexample": None,
                    "errors": [str(exc)],
                },
            )

        if not active_variables:
            equivalent = bool(left_fn() == right_fn())
            return self._result(
                status="ok" if equivalent else "observed_issue",
                conclusion=(
                    "The constant bounded property holds locally."
                    if equivalent
                    else "The constant bounded property fails locally."
                ),
                notes=["No free variables were present; the property reduced to a constant equality check."],
                result_data={
                    "backend": "hypothesis",
                    "property_holds": equivalent,
                    "counterexample": None,
                    "variables": [],
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "max_examples": sample_budget,
                    "errors": [],
                },
            )

        strategy = st.tuples(*[st.integers(domain_min, domain_max) for _ in active_variables])
        hypothesis_settings = settings(
            max_examples=sample_budget,
            derandomize=True,
            database=None,
            phases=(Phase.generate,),
        )

        try:
            counterexample_values = find(
                strategy,
                lambda values: left_fn(*values) != right_fn(*values),
                settings=hypothesis_settings,
            )
            counterexample = {
                name: value for name, value in zip(active_variables, counterexample_values, strict=True)
            }
            return self._result(
                status="observed_issue",
                conclusion="The bounded property-based search found a local counterexample.",
                notes=["Hypothesis found a counterexample within the bounded local search space."],
                result_data={
                    "backend": "hypothesis",
                    "property_holds": False,
                    "counterexample": counterexample,
                    "variables": active_variables,
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "max_examples": sample_budget,
                    "errors": [],
                },
            )
        except NoSuchExample:
            return self._result(
                status="ok",
                conclusion="The bounded property-based search found no counterexample in the local search budget.",
                notes=["No counterexample was discovered within the configured bounded Hypothesis search."],
                result_data={
                    "backend": "hypothesis",
                    "property_holds": True,
                    "counterexample": None,
                    "variables": active_variables,
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "max_examples": sample_budget,
                    "errors": [],
                },
            )
        except Exception as exc:
            return self._result(
                status="error",
                conclusion="The bounded property-based search failed during local execution.",
                notes=["The property-based runner remained local and bounded."],
                result_data={
                    "backend": "hypothesis",
                    "property_holds": None,
                    "counterexample": None,
                    "variables": active_variables,
                    "domain_min": domain_min,
                    "domain_max": domain_max,
                    "max_examples": sample_budget,
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
