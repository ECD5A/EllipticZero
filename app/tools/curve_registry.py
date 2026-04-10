from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CurveRegistryEntry(BaseModel):
    """Structured metadata entry for a known curve."""

    model_config = ConfigDict(extra="forbid")

    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    family: str
    usage_category: list[str] = Field(default_factory=list)
    field_type: str
    short_description: str
    notes: str
    field_modulus_hex: str | None = None
    a_hex: str | None = None
    b_hex: str | None = None
    generator_x_hex: str | None = None
    generator_y_hex: str | None = None
    order_hex: str | None = None
    cofactor: int | None = None
    supports_on_curve_check: bool = False


class CurveRegistry:
    """Central registry for named-curve metadata and alias resolution."""

    def __init__(self) -> None:
        self._entries = self._build_entries()
        self._alias_map = self._build_alias_map(self._entries)

    def resolve(self, name: str) -> CurveRegistryEntry | None:
        key = name.strip().lower()
        canonical = self._alias_map.get(key)
        if canonical is None:
            return None
        return self._entries[canonical]

    def list_entries(self) -> list[CurveRegistryEntry]:
        return [self._entries[name] for name in sorted(self._entries)]

    def known_names(self) -> list[str]:
        return sorted(self._alias_map)

    def _build_entries(self) -> dict[str, CurveRegistryEntry]:
        entries = [
            CurveRegistryEntry(
                canonical_name="secp256k1",
                aliases=["bitcoin-secp256k1"],
                family="secp",
                usage_category=["blockchain", "signatures"],
                field_type="prime_field",
                short_description="Koblitz-style curve used heavily in blockchain systems.",
                notes="Common in Bitcoin-style ECDSA workflows and public-key tooling.",
                field_modulus_hex="FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F",
                a_hex="0",
                b_hex="7",
                generator_x_hex="79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                generator_y_hex="483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
                order_hex="FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
                cofactor=1,
                supports_on_curve_check=True,
            ),
            CurveRegistryEntry(
                canonical_name="secp256r1",
                aliases=["p-256", "p256", "prime256v1"],
                family="secp",
                usage_category=["standards", "signatures", "ssh"],
                field_type="prime_field",
                short_description="NIST P-256 prime-field curve.",
                notes="Widely used in standards-based signatures, TLS, and device cryptography.",
                field_modulus_hex="FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF",
                a_hex="FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC",
                b_hex="5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B",
                generator_x_hex="6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296",
                generator_y_hex="4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5",
                order_hex="FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
                cofactor=1,
                supports_on_curve_check=True,
            ),
            CurveRegistryEntry(
                canonical_name="x25519",
                aliases=["curve25519"],
                family="25519",
                usage_category=["key_exchange", "standards"],
                field_type="prime_field",
                short_description="Montgomery-form curve used for key exchange style operations.",
                notes="Commonly referenced in X25519 key exchange workflows.",
                cofactor=8,
            ),
            CurveRegistryEntry(
                canonical_name="ed25519",
                aliases=[],
                family="25519",
                usage_category=["signatures", "ssh"],
                field_type="prime_field",
                short_description="Edwards-form curve commonly used for deterministic signatures.",
                notes="Frequently used in modern signature systems and SSH identities.",
                cofactor=8,
            ),
            CurveRegistryEntry(
                canonical_name="secp384r1",
                aliases=["p-384", "p384"],
                family="secp",
                usage_category=["standards", "signatures"],
                field_type="prime_field",
                short_description="NIST P-384 prime-field curve.",
                notes="Used where higher security margins than P-256 are preferred.",
                cofactor=1,
            ),
            CurveRegistryEntry(
                canonical_name="secp521r1",
                aliases=["p-521", "p521"],
                family="secp",
                usage_category=["standards", "signatures"],
                field_type="prime_field",
                short_description="NIST P-521 prime-field curve.",
                notes="Large prime-field curve used in some high-assurance standards contexts.",
                cofactor=1,
            ),
        ]
        return {entry.canonical_name: entry for entry in entries}

    def _build_alias_map(
        self,
        entries: dict[str, CurveRegistryEntry],
    ) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for entry in entries.values():
            alias_map[entry.canonical_name.lower()] = entry.canonical_name
            for alias in entry.aliases:
                alias_map[alias.lower()] = entry.canonical_name
        return alias_map


CURVE_REGISTRY = CurveRegistry()
