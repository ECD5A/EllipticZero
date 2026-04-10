from __future__ import annotations

import random
from typing import Any

from app.tools.curve_registry import CURVE_REGISTRY
from app.tools.ecc_utils import analyze_ecc_shape_invariants, describe_ecc_point_input


class FuzzRunner:
    """Deterministic local mutation probes for bounded defensive research."""

    def __init__(self, *, enabled: bool = True, max_mutations: int = 12, seed: int = 1337) -> None:
        self.enabled = enabled
        self.max_mutations = max_mutations
        self.seed = seed

    def is_available(self) -> bool:
        return self.enabled

    def run_mutation_probe(
        self,
        *,
        target_kind: str,
        seed_input: str,
        mutations: int | None = None,
        curve_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The bounded fuzz mutation path is disabled in the current configuration.",
                notes=["Enable local_research.fuzz_enabled to allow deterministic local mutation probes."],
                result_data={"mutations_generated": 0, "anomaly_count": 0, "cases": []},
            )
        mutation_budget = max(1, min(mutations or self.max_mutations, self.max_mutations))
        candidates = (
            self._curve_mutations(seed_input, mutation_budget)
            if target_kind == "curve_name"
            else self._point_mutations(seed_input, mutation_budget)
        )
        cases: list[dict[str, Any]] = []
        anomaly_count = 0

        for mutated in candidates:
            if target_kind == "curve_name":
                resolved = CURVE_REGISTRY.resolve(mutated)
                anomaly = resolved is None
                if anomaly:
                    anomaly_count += 1
                cases.append(
                    {
                        "mutated_input": mutated,
                        "resolved_curve_name": resolved.canonical_name if resolved is not None else None,
                        "anomaly_detected": anomaly,
                    }
                )
                continue

            descriptor = describe_ecc_point_input({"public_key_hex": mutated, "curve_name": curve_name})
            invariants, _ = analyze_ecc_shape_invariants(descriptor=descriptor, curve_name=curve_name)
            issues = list(invariants.get("issues", []))
            anomaly = descriptor.input_kind in {"malformed", "unknown"} or bool(issues)
            if anomaly:
                anomaly_count += 1
            cases.append(
                {
                    "mutated_input": mutated,
                    "input_kind": descriptor.input_kind,
                    "encoding": descriptor.encoding,
                    "prefix_valid": invariants.get("prefix_valid"),
                    "issues": issues,
                    "anomaly_detected": anomaly,
                }
            )

        return self._result(
            status="ok" if anomaly_count == 0 else "observed_issue",
            conclusion=(
                "Deterministic local mutation probes found no anomaly signal."
                if anomaly_count == 0
                else "Deterministic local mutation probes produced anomaly-bearing mutated cases."
            ),
            notes=["This runner performs only bounded deterministic local mutations."],
            result_data={
                "target_kind": target_kind,
                "seed_input": seed_input,
                "curve_name": curve_name,
                "mutations_generated": len(candidates),
                "anomaly_count": anomaly_count,
                "cases": cases,
            },
        )

    def _point_mutations(self, seed_input: str, mutation_budget: int) -> list[str]:
        normalized = seed_input.strip().lower().replace("0x", "")
        rng = random.Random(self.seed)
        candidates: list[str] = []
        if normalized:
            candidates.extend(
                [
                    ("05" + normalized[2:]) if len(normalized) >= 2 else normalized + "05",
                    normalized[:-2] if len(normalized) > 2 else normalized,
                    normalized + "00",
                    normalized[:4] + "gg" + normalized[6:] if len(normalized) >= 6 else normalized + "gg",
                    normalized[1:] if len(normalized) > 1 else normalized,
                ]
            )
        alphabet = "0123456789abcdef"
        while len(candidates) < mutation_budget:
            chars = list(normalized or "0279be")
            index = rng.randrange(len(chars))
            chars[index] = rng.choice(alphabet + "g")
            candidates.append("".join(chars))
        return list(dict.fromkeys(candidates))[:mutation_budget]

    def _curve_mutations(self, seed_input: str, mutation_budget: int) -> list[str]:
        normalized = seed_input.strip()
        candidates = [
            normalized.upper(),
            normalized.lower(),
            normalized.replace("-", ""),
            normalized.replace("secp", "sec"),
            normalized + "-alt",
            normalized[:-1] if normalized else normalized,
        ]
        return list(dict.fromkeys(item for item in candidates if item))[:mutation_budget]

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
