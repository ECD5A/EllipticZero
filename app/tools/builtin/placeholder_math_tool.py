from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.tools.base import BaseTool


class PlaceholderMathTool(BaseTool):
    """
    Deterministic placeholder local tool.

    This tool does not claim mathematical validation. It produces a small,
    reproducible evidence baseline from the seed and selected hypothesis.
    """

    name = "placeholder_math_tool"
    category = "heuristic"
    description = "Classify the seed text and extract basic research signals."
    input_schema_hint = "seed_text plus optional hypothesis context"
    output_schema_hint = "keyword classification summary with notes"

    KEYWORDS = {
        "elliptic",
        "curve",
        "point",
        "scalar",
        "subgroup",
        "torsion",
        "signature",
        "ecdsa",
        "ecdh",
        "implementation",
        "anomaly",
        "overflow",
        "coordinate",
        "generator",
        "secp256k1",
        "curve25519",
        "ed25519",
        "p256",
    }

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        seed_text = str(payload.get("seed_text", ""))
        words = re.findall(r"[a-z0-9_]+", seed_text.lower())
        matched_keywords = sorted({word for word in words if word in self.KEYWORDS})

        return self.make_result(
            status="ok",
            conclusion="Placeholder local analysis classified seed-level technical signals.",
            notes=[
                "Placeholder local analysis only. It classifies text-level research "
                "signals and must not be treated as proof or vulnerability evidence."
            ],
            result_data={
                "text_length": len(seed_text),
                "word_count": len(words),
                "matched_keywords": matched_keywords,
                "keyword_hit_count": len(matched_keywords),
                "contains_curve_name": any(
                    word in matched_keywords
                    for word in {"secp256k1", "curve25519", "ed25519", "p256"}
                ),
                "manual_review_recommended": len(matched_keywords) < 2,
            },
        )
