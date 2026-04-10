from __future__ import annotations

import re
from collections.abc import Mapping

from app.models.ecc_domain import ECCDomainParameters
from app.models.ecc_point import ECCPointDescriptor
from app.tools.curve_registry import CURVE_REGISTRY, CurveRegistryEntry


def resolve_ecc_domain(curve_name: str) -> ECCDomainParameters | None:
    entry = CURVE_REGISTRY.resolve(curve_name)
    if entry is None:
        return None
    return domain_from_registry_entry(entry)


def domain_from_registry_entry(entry: CurveRegistryEntry) -> ECCDomainParameters:
    return ECCDomainParameters(
        canonical_curve_name=entry.canonical_name,
        aliases=entry.aliases,
        family=entry.family,
        usage_category=entry.usage_category,
        field_type=entry.field_type,
        field_modulus_hex=entry.field_modulus_hex,
        a_hex=entry.a_hex,
        b_hex=entry.b_hex,
        generator_x_hex=entry.generator_x_hex,
        generator_y_hex=entry.generator_y_hex,
        order_hex=entry.order_hex,
        cofactor=entry.cofactor,
        short_description=entry.short_description,
        notes=entry.notes,
        supports_on_curve_check=entry.supports_on_curve_check,
    )


def normalize_hex(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    return normalized or None


def is_hex(value: str | None) -> bool:
    return bool(value) and all(char in "0123456789abcdef" for char in value)


def expected_coordinate_hex_length(
    *,
    curve_name: str | None = None,
    descriptor: ECCPointDescriptor | None = None,
) -> int | None:
    if curve_name:
        domain = resolve_ecc_domain(curve_name)
        if domain is not None and domain.field_modulus_hex:
            return len(domain.field_modulus_hex)
    if descriptor is not None and descriptor.encoding in {"compressed", "uncompressed"}:
        if descriptor.likely_curve_family == "secp":
            return 64
    if descriptor is not None and descriptor.x_hex and descriptor.y_hex and len(descriptor.x_hex) == len(descriptor.y_hex):
        return len(descriptor.x_hex)
    return None


def extract_xy_from_payload(payload: Mapping[str, object]) -> tuple[str | None, str | None]:
    if "x" in payload and "y" in payload:
        return normalize_hex(str(payload.get("x"))), normalize_hex(str(payload.get("y")))

    coordinates = payload.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        return normalize_hex(str(coordinates[0])), normalize_hex(str(coordinates[1]))

    point_text = str(payload.get("point_text", ""))
    x_match = re.search(r"x\s*[:=]\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]+)", point_text)
    y_match = re.search(r"y\s*[:=]\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]+)", point_text)
    if x_match and y_match:
        return normalize_hex(x_match.group(1)), normalize_hex(y_match.group(1))
    return None, None


def describe_ecc_point_input(payload: Mapping[str, object]) -> ECCPointDescriptor:
    notes: list[str] = []
    public_key_hex = normalize_hex(
        str(payload.get("public_key_hex")) if payload.get("public_key_hex") is not None else None
    )
    x_hex, y_hex = extract_xy_from_payload(payload)

    if public_key_hex is not None:
        if not is_hex(public_key_hex):
            return ECCPointDescriptor(
                input_kind="malformed",
                encoding="unknown",
                hex_length=len(public_key_hex),
                coordinate_presence="missing",
                notes=["public_key_hex contains non-hexadecimal characters."],
            )
        prefix = public_key_hex[:2]
        if prefix in {"02", "03"} and len(public_key_hex) == 66:
            notes.append("Compressed short-Weierstrass public key style detected.")
            return ECCPointDescriptor(
                input_kind="public_key_hex",
                encoding="compressed",
                hex_length=len(public_key_hex),
                coordinate_presence="x_only",
                likely_curve_family="secp",
                normalized_public_key_hex=public_key_hex,
                x_hex=public_key_hex[2:],
                notes=notes,
            )
        if prefix == "04" and len(public_key_hex) == 130:
            notes.append("Uncompressed short-Weierstrass public key style detected.")
            return ECCPointDescriptor(
                input_kind="public_key_hex",
                encoding="uncompressed",
                hex_length=len(public_key_hex),
                coordinate_presence="x_and_y",
                likely_curve_family="secp",
                normalized_public_key_hex=public_key_hex,
                x_hex=public_key_hex[2:66],
                y_hex=public_key_hex[66:130],
                notes=notes,
            )
        return ECCPointDescriptor(
            input_kind="unknown",
            encoding="unknown",
            hex_length=len(public_key_hex),
            coordinate_presence="missing",
            normalized_public_key_hex=public_key_hex,
            notes=["Point-like hex input does not match supported compressed or uncompressed formats."],
        )

    if x_hex is not None and y_hex is not None:
        if is_hex(x_hex) and is_hex(y_hex):
            notes.append("Coordinate payload is hex-like.")
            if len(x_hex) == len(y_hex) == 64:
                notes.append("Coordinate size matches common 256-bit short-Weierstrass curves.")
            return ECCPointDescriptor(
                input_kind="coordinate_payload",
                encoding="coordinates",
                hex_length=len(x_hex) + len(y_hex),
                coordinate_presence="x_and_y",
                likely_curve_family="secp" if len(x_hex) == len(y_hex) == 64 else None,
                x_hex=x_hex,
                y_hex=y_hex,
                notes=notes,
            )
        return ECCPointDescriptor(
            input_kind="malformed",
            encoding="coordinates",
            hex_length=None,
            coordinate_presence="x_and_y",
            x_hex=x_hex,
            y_hex=y_hex,
            notes=["Coordinate payload contains non-hexadecimal characters."],
        )

    return ECCPointDescriptor(
        input_kind="unknown",
        encoding="unknown",
        hex_length=None,
        coordinate_presence="missing",
        notes=["Input does not contain a supported public-key hex or x/y coordinate form."],
    )


def analyze_ecc_shape_invariants(
    *,
    descriptor: ECCPointDescriptor,
    curve_name: str | None = None,
) -> tuple[dict[str, object], list[str]]:
    notes = list(descriptor.notes)
    issues: list[str] = []
    prefix = (
        descriptor.normalized_public_key_hex[:2]
        if descriptor.normalized_public_key_hex
        else None
    )
    expected_length = expected_coordinate_hex_length(curve_name=curve_name, descriptor=descriptor)

    prefix_valid: bool | None = None
    if descriptor.encoding == "compressed":
        prefix_valid = prefix in {"02", "03"}
        if prefix_valid:
            notes.append("Compressed key prefix is one of the supported short-Weierstrass forms.")
        else:
            issues.append("Compressed key prefix is not one of the supported short-Weierstrass forms.")
    elif descriptor.encoding == "uncompressed":
        prefix_valid = prefix == "04"
        if prefix_valid:
            notes.append("Uncompressed key prefix matches the standard short-Weierstrass form.")
        else:
            issues.append("Uncompressed key prefix does not match the standard short-Weierstrass form.")
    elif descriptor.normalized_public_key_hex is not None and descriptor.hex_length == 66:
        prefix_valid = prefix in {"02", "03"}
        if prefix_valid is False:
            issues.append("Compressed-length point-like input uses an invalid prefix byte.")
    elif descriptor.normalized_public_key_hex is not None and descriptor.hex_length == 130:
        prefix_valid = prefix == "04"
        if prefix_valid is False:
            issues.append("Uncompressed-length point-like input uses an invalid prefix byte.")

    coordinate_lengths = [len(value) for value in (descriptor.x_hex, descriptor.y_hex) if value]
    coordinate_length_match = (
        len(coordinate_lengths) == 2 and coordinate_lengths[0] == coordinate_lengths[1]
    )
    if descriptor.coordinate_presence == "x_and_y":
        if coordinate_length_match:
            notes.append("Coordinate lengths match.")
        else:
            issues.append("Coordinate lengths do not match.")

    expected_length_match: bool | None = None
    if expected_length is not None:
        if descriptor.encoding == "compressed" and descriptor.x_hex is not None:
            expected_length_match = len(descriptor.x_hex) == expected_length
        elif descriptor.coordinate_presence == "x_and_y" and descriptor.x_hex and descriptor.y_hex:
            expected_length_match = (
                len(descriptor.x_hex) == expected_length and len(descriptor.y_hex) == expected_length
            )
        if expected_length_match is True:
            notes.append(f"Coordinate width matches the expected bounded width {expected_length}.")
        elif expected_length_match is False:
            issues.append(f"Coordinate width does not match the expected bounded width {expected_length}.")

    invariant_data: dict[str, object] = {
        "prefix": prefix,
        "prefix_valid": prefix_valid,
        "expected_coordinate_hex_length": expected_length,
        "coordinate_length_match": coordinate_length_match,
        "expected_length_match": expected_length_match,
        "x_hex_length": len(descriptor.x_hex) if descriptor.x_hex is not None else None,
        "y_hex_length": len(descriptor.y_hex) if descriptor.y_hex is not None else None,
        "issues": issues,
    }
    return invariant_data, notes


def bounded_field_range_check(
    *,
    curve_name: str | None,
    x_hex: str | None,
    y_hex: str | None,
) -> tuple[dict[str, object], list[str]]:
    if curve_name is None:
        return {
            "field_bounds_checked": False,
            "x_in_field_range": None,
            "y_in_field_range": None,
        }, []

    domain = resolve_ecc_domain(curve_name)
    if domain is None or not domain.field_modulus_hex:
        return {
            "field_bounds_checked": False,
            "x_in_field_range": None,
            "y_in_field_range": None,
        }, ["Field-range sanity checks were unavailable because the curve domain was not fully resolved."]

    if x_hex is None and y_hex is None:
        return {
            "field_bounds_checked": False,
            "x_in_field_range": None,
            "y_in_field_range": None,
        }, ["Field-range sanity checks require at least one coordinate."]

    if (x_hex is not None and not is_hex(x_hex)) or (y_hex is not None and not is_hex(y_hex)):
        return {
            "field_bounds_checked": False,
            "x_in_field_range": None,
            "y_in_field_range": None,
        }, ["Field-range sanity checks require hexadecimal coordinate inputs."]

    modulus = int(domain.field_modulus_hex, 16)
    x_in_range = int(x_hex, 16) < modulus if x_hex is not None else None
    y_in_range = int(y_hex, 16) < modulus if y_hex is not None else None
    notes = ["Bounded field-range sanity check performed against the local curve modulus."]
    if x_in_range is False or y_in_range is False:
        notes.append("One or more coordinates exceed the field modulus range.")
    return {
        "field_bounds_checked": True,
        "x_in_field_range": x_in_range,
        "y_in_field_range": y_in_range,
    }, notes


def short_weierstrass_on_curve_check(
    *,
    curve_name: str,
    x_hex: str | None,
    y_hex: str | None,
) -> tuple[bool | None, list[str]]:
    domain = resolve_ecc_domain(curve_name)
    if domain is None:
        return None, ["Curve name was not recognized by the ECC domain layer."]
    if not domain.supports_on_curve_check:
        return None, ["On-curve checks are not supported for this curve family in the bounded V8 layer."]
    if not domain.field_modulus_hex or not domain.a_hex or not domain.b_hex:
        return None, ["The selected curve does not expose enough domain parameters for an on-curve check."]
    if x_hex is None or y_hex is None:
        return None, ["Complete x/y coordinates are required for a bounded on-curve check."]
    if not is_hex(x_hex) or not is_hex(y_hex):
        return None, ["On-curve checking requires hexadecimal x/y coordinates."]

    p = int(domain.field_modulus_hex, 16)
    a = int(domain.a_hex, 16)
    b = int(domain.b_hex, 16)
    x_value = int(x_hex, 16)
    y_value = int(y_hex, 16)
    lhs = pow(y_value, 2, p)
    rhs = (pow(x_value, 3, p) + (a * x_value) + b) % p
    return lhs == rhs, ["Bounded short-Weierstrass on-curve check performed locally."]
