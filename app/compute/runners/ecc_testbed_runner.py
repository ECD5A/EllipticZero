from __future__ import annotations

from typing import Any

from app.tools.curve_registry import CURVE_REGISTRY
from app.tools.ecc_utils import (
    analyze_ecc_shape_invariants,
    bounded_field_range_check,
    describe_ecc_point_input,
)


class ECCTestbedRunner:
    """Run built-in bounded ECC testbed suites locally."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled

    def run_testbed(self, *, testbed_name: str, case_limit: int = 8) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The built-in ECC testbed layer is disabled in the current configuration.",
                notes=["Enable local_research.ecc_testbeds_enabled to allow bounded local testbed sweeps."],
                result_data={"testbed_name": testbed_name, "case_count": 0, "anomaly_count": 0, "cases": []},
            )

        handlers = {
            "point_anomaly_corpus": self._point_anomaly_corpus,
            "curve_alias_corpus": self._curve_alias_corpus,
            "coordinate_shape_corpus": self._coordinate_shape_corpus,
            "curve_domain_corpus": self._curve_domain_corpus,
            "encoding_edge_corpus": self._encoding_edge_corpus,
            "subgroup_cofactor_corpus": self._subgroup_cofactor_corpus,
            "curve_family_corpus": self._curve_family_corpus,
            "twist_hygiene_corpus": self._twist_hygiene_corpus,
            "domain_completeness_corpus": self._domain_completeness_corpus,
            "family_transition_corpus": self._family_transition_corpus,
        }
        if testbed_name not in handlers:
            return self._result(
                status="invalid_input",
                conclusion="The requested ECC testbed name is not supported by the local bounded testbed layer.",
                notes=["Use a supported built-in testbed name."],
                result_data={"testbed_name": testbed_name, "case_count": 0, "anomaly_count": 0, "cases": []},
            )

        cases = handlers[testbed_name]()[: max(1, min(case_limit, 16))]
        anomaly_count = sum(1 for case in cases if case.get("anomaly_detected"))
        issue_type_counts = self._issue_type_counts(cases)
        anomaly_case_ids = [str(case["case_id"]) for case in cases if case.get("anomaly_detected")]
        return self._result(
            status="ok" if anomaly_count == 0 else "observed_issue",
            conclusion=(
                "The bounded ECC testbed sweep found no anomaly signal."
                if anomaly_count == 0
                else "The bounded ECC testbed sweep surfaced anomaly-bearing cases."
            ),
            notes=["This runner executes only built-in local ECC testbed corpora."],
            result_data={
                "testbed_name": testbed_name,
                "case_count": len(cases),
                "anomaly_count": anomaly_count,
                "anomaly_case_ids": anomaly_case_ids,
                "issue_type_counts": issue_type_counts,
                "cases": cases,
            },
        )

    def _point_anomaly_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_point_case(
                case_id="valid_compressed",
                payload={
                    "public_key_hex": "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="valid_uncompressed",
                payload={
                    "public_key_hex": (
                        "046B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296"
                        "4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5"
                    ),
                    "curve_name": "secp256r1",
                },
                curve_name="secp256r1",
            ),
            self._build_point_case(
                case_id="bad_prefix",
                payload={
                    "public_key_hex": "0579BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="bad_uncompressed_prefix",
                payload={
                    "public_key_hex": (
                        "056B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296"
                        "4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5"
                    ),
                    "curve_name": "secp256r1",
                },
                curve_name="secp256r1",
            ),
            self._build_point_case(
                case_id="malformed_hex",
                payload={"public_key_hex": "04zz", "curve_name": "secp256r1"},
                curve_name="secp256r1",
            ),
            self._build_point_case(
                case_id="coordinate_length_mismatch",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "483ADA7726A3C4655DA4FBFC0E1108A8",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="x_out_of_field_range",
                payload={
                    "x": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC30",
                    "y": "483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
        ]

    def _coordinate_shape_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_point_case(
                case_id="balanced_256bit_coordinates",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="short_y_coordinate",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "483ADA7726A3C4655DA4FBFC0E1108A8",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="non_hex_coordinate",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "GGGADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="y_out_of_field_range",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC30",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
        ]

    def _curve_alias_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "P-256", "prime256v1", "curve25519", "x25519", "not_a_curve"]
        cases: list[dict[str, Any]] = []
        for curve_name in names:
            resolved = CURVE_REGISTRY.resolve(curve_name)
            anomaly = resolved is None
            issues = [] if not anomaly else ["Curve name did not resolve to a known local registry entry."]
            cases.append(
                {
                    "case_id": curve_name,
                    "input_curve_name": curve_name,
                    "resolved_curve_name": resolved.canonical_name if resolved is not None else None,
                    "family": resolved.family if resolved is not None else None,
                    "alias_form": (
                        curve_name.strip().lower() != resolved.canonical_name.lower()
                        if resolved is not None
                        else None
                    ),
                    "supports_on_curve_check": (
                        resolved.supports_on_curve_check if resolved is not None else None
                    ),
                    "issues": issues,
                    "anomaly_detected": anomaly,
                }
            )
        return cases

    def _curve_domain_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "secp256r1", "secp384r1", "secp521r1", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for curve_name in names:
            resolved = CURVE_REGISTRY.resolve(curve_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": curve_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "missing_core_fields": [],
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            missing_fields = [
                field_name
                for field_name, value in (
                    ("field_modulus_hex", resolved.field_modulus_hex),
                    ("generator_x_hex", resolved.generator_x_hex),
                    ("generator_y_hex", resolved.generator_y_hex),
                    ("order_hex", resolved.order_hex),
                    ("cofactor", resolved.cofactor),
                )
                if value in (None, "", [])
            ]
            issues: list[str] = []
            anomaly = False
            if resolved.family == "secp" and missing_fields:
                issues.append(
                    "Short-Weierstrass registry entry is missing bounded domain fields: "
                    + ", ".join(missing_fields)
                )
                anomaly = True
            cases.append(
                {
                    "case_id": curve_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "supports_on_curve_check": resolved.supports_on_curve_check,
                    "missing_core_fields": missing_fields,
                    "issues": issues,
                    "anomaly_detected": anomaly,
                }
            )
        return cases

    def _encoding_edge_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_point_case(
                case_id="compressed_k1_generator",
                payload={
                    "public_key_hex": "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="uncompressed_p256_generator",
                payload={
                    "public_key_hex": (
                        "046B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296"
                        "4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5"
                    ),
                    "curve_name": "secp256r1",
                },
                curve_name="secp256r1",
            ),
            self._build_point_case(
                case_id="hybrid_prefix_candidate",
                payload={
                    "public_key_hex": (
                        "0679BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
                    ),
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
            self._build_point_case(
                case_id="x25519_like_public_key",
                payload={
                    "public_key_hex": "A546E36BFBD39B8F0D6D25D76C6F7C14E2A3BADC0A4C2AE44C0A4D1D6E5F6071",
                    "curve_name": "x25519",
                },
                curve_name="x25519",
            ),
            self._build_point_case(
                case_id="ed25519_like_public_key",
                payload={
                    "public_key_hex": "D75A980182B10AB7D54BFED3C964073A0EE172F3DAA62325AF021A68F707511A",
                    "curve_name": "ed25519",
                },
                curve_name="ed25519",
            ),
            self._build_point_case(
                case_id="non_hex_coordinate_payload",
                payload={
                    "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    "y": "not_hex_coordinate",
                    "curve_name": "secp256k1",
                },
                curve_name="secp256k1",
            ),
        ]

    def _subgroup_cofactor_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "secp256r1", "secp384r1", "secp521r1", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for curve_name in names:
            resolved = CURVE_REGISTRY.resolve(curve_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": curve_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "cofactor": None,
                        "supports_on_curve_check": None,
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            issues: list[str] = []
            if resolved.cofactor not in (None, 1):
                issues.append(
                    f"Curve uses cofactor {resolved.cofactor}; subgroup membership and cofactor clearing require manual review."
                )
            if resolved.family == "25519":
                issues.append(
                    "25519-family inputs may require subgroup or twist hygiene that is not validated by short-Weierstrass checks."
                )
            if not resolved.supports_on_curve_check:
                issues.append(
                    "Local bounded on-curve checks are unavailable for this family, so subgroup assumptions remain partially unvalidated."
                )
            if not resolved.order_hex:
                issues.append("Curve registry entry does not expose order metadata for bounded subgroup reasoning.")
            cases.append(
                {
                    "case_id": curve_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "cofactor": resolved.cofactor,
                    "supports_on_curve_check": resolved.supports_on_curve_check,
                    "issues": issues,
                    "anomaly_detected": bool(issues),
                }
            )
        return cases

    def _curve_family_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "prime256v1", "secp384r1", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for input_name in names:
            resolved = CURVE_REGISTRY.resolve(input_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": input_name,
                        "input_curve_name": input_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            missing_fields = [
                field_name
                for field_name, value in (
                    ("field_modulus_hex", resolved.field_modulus_hex),
                    ("generator_x_hex", resolved.generator_x_hex),
                    ("generator_y_hex", resolved.generator_y_hex),
                    ("order_hex", resolved.order_hex),
                )
                if value in (None, "", [])
            ]
            issues: list[str] = []
            alias_form = input_name.strip().lower() != resolved.canonical_name.lower()
            if resolved.family == "25519":
                issues.append(
                    "Curve family requires non-short-Weierstrass handling; bounded format and on-curve checks remain family-limited."
                )
            if resolved.family == "secp" and missing_fields:
                issues.append(
                    "Short-Weierstrass family entry is missing bounded domain metadata: "
                    + ", ".join(missing_fields)
                )
            if alias_form:
                issues.append("Alias form resolved correctly, but downstream handling should still confirm canonical family assumptions.")
            cases.append(
                {
                    "case_id": input_name,
                    "input_curve_name": input_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "alias_form": alias_form,
                    "issues": issues,
                    "anomaly_detected": bool(issues),
                }
            )
        return cases

    def _twist_hygiene_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "secp256r1", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for curve_name in names:
            resolved = CURVE_REGISTRY.resolve(curve_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": curve_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "cofactor": None,
                        "supports_on_curve_check": None,
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            issues: list[str] = []
            if resolved.family == "25519":
                issues.append(
                    "25519-family inputs keep twist and small-subgroup assumptions separate from short-Weierstrass validation paths."
                )
            if resolved.cofactor not in (None, 1):
                issues.append(
                    f"Curve uses cofactor {resolved.cofactor}; explicit cofactor-clearing or subgroup-membership reasoning remains required."
                )
            if not resolved.supports_on_curve_check:
                issues.append(
                    "Bounded on-curve validation is unavailable for this family, so twist-hygiene assumptions remain manual-review items."
                )
            cases.append(
                {
                    "case_id": curve_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "cofactor": resolved.cofactor,
                    "supports_on_curve_check": resolved.supports_on_curve_check,
                    "issues": issues,
                    "anomaly_detected": bool(issues),
                }
            )
        return cases

    def _domain_completeness_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "secp256r1", "secp384r1", "secp521r1", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for curve_name in names:
            resolved = CURVE_REGISTRY.resolve(curve_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": curve_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "missing_core_fields": [],
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            missing_fields = [
                field_name
                for field_name, value in (
                    ("field_modulus_hex", resolved.field_modulus_hex),
                    ("generator_x_hex", resolved.generator_x_hex),
                    ("generator_y_hex", resolved.generator_y_hex),
                    ("order_hex", resolved.order_hex),
                    ("cofactor", resolved.cofactor),
                )
                if value in (None, "", [])
            ]
            issues: list[str] = []
            if missing_fields:
                issues.append(
                    "Curve registry entry remains only partially specified for bounded domain reasoning: "
                    + ", ".join(missing_fields)
                )
            if resolved.family == "25519":
                issues.append(
                    "25519-family handling still needs family-specific domain assumptions because short-Weierstrass generator or order expectations do not transfer cleanly."
                )
            cases.append(
                {
                    "case_id": curve_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "supports_on_curve_check": resolved.supports_on_curve_check,
                    "missing_core_fields": missing_fields,
                    "issues": issues,
                    "anomaly_detected": bool(issues),
                }
            )
        return cases

    def _family_transition_corpus(self) -> list[dict[str, Any]]:
        names = ["secp256k1", "prime256v1", "curve25519", "x25519", "ed25519"]
        cases: list[dict[str, Any]] = []
        for input_name in names:
            resolved = CURVE_REGISTRY.resolve(input_name)
            if resolved is None:
                cases.append(
                    {
                        "case_id": input_name,
                        "input_curve_name": input_name,
                        "resolved_curve_name": None,
                        "family": None,
                        "curve_form": None,
                        "issues": ["Curve name did not resolve to a known local registry entry."],
                        "anomaly_detected": True,
                    }
                )
                continue

            alias_form = input_name.strip().lower() != resolved.canonical_name.lower()
            curve_form = self._curve_form_label(resolved.canonical_name, resolved.family)
            issues: list[str] = []
            if alias_form:
                issues.append(
                    "Alias resolved to a canonical curve name, but downstream family transitions still require explicit normalization."
                )
            if resolved.family == "25519":
                issues.append(
                    f"{curve_form} handling stays family-specific; short-Weierstrass parsing and validation expectations do not transfer directly."
                )
            if not resolved.supports_on_curve_check:
                issues.append(
                    "Bounded on-curve validation is unavailable for this family, so transition checks remain partially manual."
                )
            cases.append(
                {
                    "case_id": input_name,
                    "input_curve_name": input_name,
                    "resolved_curve_name": resolved.canonical_name,
                    "family": resolved.family,
                    "curve_form": curve_form,
                    "alias_form": alias_form,
                    "issues": issues,
                    "anomaly_detected": bool(issues),
                }
            )
        return cases

    def _build_point_case(
        self,
        *,
        case_id: str,
        payload: dict[str, str],
        curve_name: str | None,
    ) -> dict[str, Any]:
        descriptor = describe_ecc_point_input(payload)
        invariants, _ = analyze_ecc_shape_invariants(descriptor=descriptor, curve_name=curve_name)
        field_range, _ = bounded_field_range_check(
            curve_name=curve_name,
            x_hex=descriptor.x_hex,
            y_hex=descriptor.y_hex,
        )
        issues = list(invariants.get("issues", []))
        if descriptor.input_kind == "malformed":
            issues.append("Input contains malformed hexadecimal or coordinate data.")
        elif descriptor.input_kind == "unknown":
            issues.append("Point-like input did not match a supported bounded point encoding.")
        if field_range.get("x_in_field_range") is False:
            issues.append("x coordinate exceeds the local field modulus.")
        if field_range.get("y_in_field_range") is False:
            issues.append("y coordinate exceeds the local field modulus.")
        deduped_issues = list(dict.fromkeys(issues))
        return {
            "case_id": case_id,
            "curve_name": curve_name,
            "input_kind": descriptor.input_kind,
            "encoding": descriptor.encoding,
            "prefix_valid": invariants.get("prefix_valid"),
            "coordinate_length_match": invariants.get("coordinate_length_match"),
            "x_hex_length": invariants.get("x_hex_length"),
            "y_hex_length": invariants.get("y_hex_length"),
            "field_bounds_checked": field_range.get("field_bounds_checked"),
            "x_in_field_range": field_range.get("x_in_field_range"),
            "y_in_field_range": field_range.get("y_in_field_range"),
            "issues": deduped_issues,
            "anomaly_detected": bool(deduped_issues),
        }

    def _issue_type_counts(self, cases: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in cases:
            for issue in case.get("issues", []):
                counts[str(issue)] = counts.get(str(issue), 0) + 1
        return counts

    def _curve_form_label(self, canonical_name: str, family: str) -> str:
        lowered = canonical_name.strip().lower()
        if lowered == "x25519":
            return "Montgomery-family"
        if lowered == "ed25519":
            return "Edwards-family"
        if family == "secp":
            return "short-Weierstrass"
        if family == "25519":
            return "25519-family"
        return "family-specific"

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
