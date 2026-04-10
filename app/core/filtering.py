from __future__ import annotations

import re

from app.core.seed_parsing import extract_contract_code

GENERIC_REQUESTS = {
    "help",
    "analyze this",
    "research this",
    "do research",
    "something with curves",
    "elliptic curve",
    "crypto idea",
}

TECHNICAL_TERMS = {
    "curve",
    "point",
    "elliptic",
    "ecdsa",
    "ecdh",
    "signature",
    "implementation",
    "anomaly",
    "secp256k1",
    "curve25519",
    "ed25519",
    "torsion",
    "scalar",
    "subgroup",
    "coordinate",
    "contract",
    "solidity",
    "vyper",
    "reentrancy",
    "delegatecall",
    "tx.origin",
    "access",
    "modifier",
}


def is_extremely_vague_request(seed_text: str) -> bool:
    """Reject underspecified inputs that cannot support a bounded session."""

    normalized = " ".join(seed_text.lower().split())
    tokens = re.findall(r"[a-z0-9_]+", normalized)

    if normalized in GENERIC_REQUESTS:
        return True
    if len(tokens) < 3:
        return True
    if len(tokens) < 5 and not any(token in TECHNICAL_TERMS for token in tokens):
        return True
    return False


def validate_seed_text(seed_text: str) -> str:
    """Validate and normalize the user-provided research idea."""

    stripped = seed_text.strip()
    if not stripped:
        raise ValueError("Research idea cannot be empty.")
    if extract_contract_code(stripped):
        return stripped
    if is_extremely_vague_request(stripped):
        raise ValueError(
            "Research idea is too vague. Include a curve, contract behavior, point behavior, "
            "implementation detail, anomaly, or testable mathematical/security property."
        )
    return stripped
