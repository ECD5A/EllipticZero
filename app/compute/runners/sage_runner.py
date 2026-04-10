from __future__ import annotations

import shutil
from typing import Any

from sympy import SympifyError, simplify, sympify


class SageRunner:
    """Foundation adapter for bounded Sage or Sage-compatible experiments."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        binary: str = "sage",
        timeout_seconds: int = 30,
    ) -> None:
        self.enabled = enabled
        self.binary = binary
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        return shutil.which(self.binary) is not None

    def run_symbolic(self, expression: str) -> dict[str, Any]:
        normalized = expression.strip()
        if not self.enabled:
            return self._unavailable_result(
                conclusion="Sage-backed symbolic execution is disabled in the current configuration.",
                notes=[
                    "advanced_math_enabled path remains bounded and local.",
                    "Enable sage.enabled to allow Sage availability checks.",
                ],
            )
        if len(normalized) > 512:
            return {
                "status": "invalid_input",
                "conclusion": "The symbolic expression exceeds the bounded input size for advanced math execution.",
                "notes": ["Expression length must remain <= 512 characters."],
                "deterministic": True,
                "result_data": {
                    "sage_enabled": self.enabled,
                    "sage_available": self.is_available(),
                    "backend": "sage_adapter_foundation",
                    "parsed": False,
                    "normalized_form": None,
                    "execution_performed": False,
                    "errors": ["expression_too_large"],
                },
            }
        if not self.is_available():
            return self._unavailable_result(
                conclusion="Sage is not available locally, so the advanced symbolic path could not run.",
                notes=[
                    f"Sage binary '{self.binary}' was not found on the local PATH.",
                    "A simpler deterministic symbolic fallback may still be used by the orchestrator.",
                ],
            )

        try:
            parsed = sympify(normalized.replace("^", "**"))
            simplified = simplify(parsed)
        except (SympifyError, TypeError, ValueError) as exc:
            return {
                "status": "error",
                "conclusion": "The Sage adapter foundation could not normalize the symbolic expression.",
                "notes": [
                    "The adapter remained bounded and did not execute unrestricted external scripts.",
                ],
                "deterministic": True,
                "result_data": {
                    "sage_enabled": self.enabled,
                    "sage_available": True,
                    "backend": "sage_compatible_preview",
                    "parsed": False,
                    "normalized_form": None,
                    "execution_performed": False,
                    "errors": [str(exc)],
                },
            }

        return {
            "status": "ok",
            "conclusion": "The Sage adapter foundation produced a bounded symbolic normalization preview.",
            "notes": [
                "V6 uses a Sage-availability gate with a bounded Sage-compatible preview path.",
                "Direct unrestricted external Sage scripting remains intentionally disabled.",
            ],
            "deterministic": True,
            "result_data": {
                "sage_enabled": self.enabled,
                "sage_available": True,
                "backend": "sage_compatible_preview",
                "parsed": True,
                "normalized_form": str(simplified),
                "execution_performed": False,
                "errors": [],
            },
        }

    def _unavailable_result(self, *, conclusion: str, notes: list[str]) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "conclusion": conclusion,
            "notes": notes,
            "deterministic": True,
            "result_data": {
                "sage_enabled": self.enabled,
                "sage_available": False,
                "backend": "sage_adapter_foundation",
                "parsed": False,
                "normalized_form": None,
                "execution_performed": False,
                "errors": [],
            },
        }
