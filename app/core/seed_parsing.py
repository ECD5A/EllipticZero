from __future__ import annotations

import re
from pathlib import Path

from app.tools.curve_registry import CURVE_REGISTRY

SMART_CONTRACT_DOMAIN_MARKER = "[EZ_DOMAIN: smart_contract_audit]"
SMART_CONTRACT_LANGUAGE_PREFIX = "[EZ_CONTRACT_LANGUAGE:"
SMART_CONTRACT_SOURCE_PREFIX = "[EZ_CONTRACT_SOURCE:"
SMART_CONTRACT_ROOT_PREFIX = "[EZ_CONTRACT_ROOT:"
SMART_CONTRACT_CODE_BEGIN = "[EZ_CONTRACT_CODE_BEGIN]"
SMART_CONTRACT_CODE_END = "[EZ_CONTRACT_CODE_END]"
SMART_CONTRACT_MAX_CODE_CHARS = 20_000
SMART_CONTRACT_MAX_ROOT_SCAN_DEPTH = 3
SMART_CONTRACT_MAX_ROOT_SCAN_FILES = 64


def build_smart_contract_seed(
    *,
    idea_text: str,
    contract_code: str,
    language: str = "solidity",
    source_label: str | None = None,
    contract_root: str | None = None,
) -> str:
    normalized_idea = idea_text.strip()
    normalized_code = contract_code.strip()
    normalized_language = (language or "solidity").strip().lower()
    normalized_source = source_label.strip() if source_label else None
    normalized_root = contract_root.strip() if contract_root else None

    if not normalized_idea:
        raise ValueError("Smart contract audit idea cannot be empty.")
    if not normalized_code:
        raise ValueError("Smart contract code cannot be empty.")
    if len(normalized_code) > SMART_CONTRACT_MAX_CODE_CHARS:
        raise ValueError(
            f"Smart contract code is too large for a bounded local session ({len(normalized_code)} > {SMART_CONTRACT_MAX_CODE_CHARS})."
        )

    lines = [
        SMART_CONTRACT_DOMAIN_MARKER,
        f"{SMART_CONTRACT_LANGUAGE_PREFIX} {normalized_language}]",
    ]
    if normalized_source:
        lines.append(f"{SMART_CONTRACT_SOURCE_PREFIX} {normalized_source}]")
    if normalized_root:
        lines.append(f"{SMART_CONTRACT_ROOT_PREFIX} {normalized_root}]")
    lines.extend(
        [
            "User idea:",
            normalized_idea,
            SMART_CONTRACT_CODE_BEGIN,
            normalized_code,
            SMART_CONTRACT_CODE_END,
        ]
    )
    return "\n".join(lines)


def is_smart_contract_seed(text: str) -> bool:
    lowered = text.lower()
    return (
        SMART_CONTRACT_DOMAIN_MARKER.lower() in lowered
        or extract_contract_code(text) is not None
        or any(
            token in lowered
            for token in (
                "pragma solidity",
                "contract ",
                "interface ",
                "library ",
                "function ",
                "delegatecall",
                "tx.origin",
                "selfdestruct",
            )
        )
    )


def extract_contract_language(text: str) -> str | None:
    match = re.search(r"\[EZ_CONTRACT_LANGUAGE:\s*([^\]]+)\]", text, flags=re.IGNORECASE)
    if match is None:
        return None
    value = match.group(1).strip().lower()
    return value or None


def extract_contract_source_label(text: str) -> str | None:
    match = re.search(r"\[EZ_CONTRACT_SOURCE:\s*([^\]]+)\]", text, flags=re.IGNORECASE)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def extract_contract_root(text: str) -> str | None:
    match = re.search(r"\[EZ_CONTRACT_ROOT:\s*([^\]]+)\]", text, flags=re.IGNORECASE)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def infer_contract_root_from_source_path(source_label: str | None) -> str | None:
    if not source_label:
        return None
    try:
        source_path = Path(source_label).expanduser()
    except OSError:
        return None
    if not source_path.exists() or not source_path.is_file():
        return None

    resolved_source = source_path.resolve()
    best_candidate = resolved_source.parent
    best_contract_count = 0
    best_depth = SMART_CONTRACT_MAX_ROOT_SCAN_DEPTH + 1

    ancestor: Path | None = resolved_source.parent
    for depth in range(SMART_CONTRACT_MAX_ROOT_SCAN_DEPTH + 1):
        if ancestor is None or not ancestor.exists() or not ancestor.is_dir():
            break
        contract_files = _bounded_contract_files(ancestor)
        if len(contract_files) > SMART_CONTRACT_MAX_ROOT_SCAN_FILES:
            ancestor = ancestor.parent if ancestor.parent != ancestor else None
            continue
        if resolved_source not in contract_files:
            ancestor = ancestor.parent if ancestor.parent != ancestor else None
            continue
        contract_count = len(contract_files)
        if contract_count >= 2 and (
            contract_count > best_contract_count
            or (contract_count == best_contract_count and depth < best_depth)
        ):
            best_candidate = ancestor
            best_contract_count = contract_count
            best_depth = depth
        ancestor = ancestor.parent if ancestor.parent != ancestor else None

    return str(best_candidate)


def extract_contract_code(text: str) -> str | None:
    match = re.search(
        rf"{re.escape(SMART_CONTRACT_CODE_BEGIN)}\s*(.*?)\s*{re.escape(SMART_CONTRACT_CODE_END)}",
        text,
        flags=re.DOTALL,
    )
    if match is not None:
        value = match.group(1).strip()
        return value or None

    if any(token in text.lower() for token in ("pragma solidity", "contract ", "interface ", "library ")):
        stripped = text.strip()
        return stripped or None
    return None


def _bounded_contract_files(root_path: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.sol", "*.vy"):
        for path in root_path.rglob(pattern):
            if path.is_file():
                files.append(path.resolve())
                if len(files) > SMART_CONTRACT_MAX_ROOT_SCAN_FILES:
                    return files
    return files


def extract_contract_name(text: str) -> str | None:
    contract_code = extract_contract_code(text) or text
    for pattern in (
        r"\bcontract\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\blibrary\s+([A-Za-z_][A-Za-z0-9_]*)",
    ):
        match = re.search(pattern, contract_code)
        if match is not None:
            return match.group(1).strip()
    return None


def extract_expression_pair(text: str) -> tuple[str | None, str | None]:
    expression = extract_expression(text)
    if expression and "=" in expression:
        left, right = expression.split("=", 1)
        return left.strip(), right.strip()
    if "=" in text:
        left, right = text.split("=", 1)
        left_expr = extract_expression(left)
        right_expr = extract_expression(right)
        if left_expr and right_expr:
            return left_expr, right_expr
    return None, None


def extract_curve_name(text: str) -> str | None:
    lowered = text.lower()
    for token in re.findall(r"[a-z0-9\-_]+", lowered):
        entry = CURVE_REGISTRY.resolve(token)
        if entry is not None:
            return entry.canonical_name
    for alias in CURVE_REGISTRY.known_names():
        if alias in lowered:
            entry = CURVE_REGISTRY.resolve(alias)
            if entry is not None:
                return entry.canonical_name
    return None


def extract_point_coordinates(text: str) -> tuple[str | None, str | None]:
    x_match = re.search(r"x\s*[:=]\s*([0-9a-fA-Fx]+)", text)
    y_match = re.search(r"y\s*[:=]\s*([0-9a-fA-Fx]+)", text)
    if x_match and y_match:
        return x_match.group(1), y_match.group(1)
    return None, None


def extract_expression(text: str) -> str | None:
    equation_match = re.search(r"([A-Za-z0-9_\+\-\*/\^\(\)\s]+=[A-Za-z0-9_\+\-\*/\^\(\)\s]+)", text)
    if equation_match:
        return equation_match.group(1).strip()
    expression_match = re.search(r"([A-Za-z0-9_\+\-\*/\^\(\)\s]{3,})", text)
    if expression_match and any(symbol in expression_match.group(1) for symbol in "+-*/^"):
        return expression_match.group(1).strip()
    return None


def extract_public_key_hex(text: str) -> str | None:
    for match in re.findall(r"(?:0x)?[0-9A-Fa-f]{66,130}", text):
        normalized = match[2:] if match.lower().startswith("0x") else match
        if len(normalized) in {66, 130}:
            return normalized
    return None


def extract_modular_payload(text: str) -> tuple[int, int, int] | None:
    modulus_match = re.search(r"\bmod(?:ulus)?\s*[:=]?\s*(\d+)\b", text, flags=re.IGNORECASE)
    if modulus_match is None:
        modulus_match = re.search(r"\bmod\s+(\d+)\b", text, flags=re.IGNORECASE)
    if modulus_match is None:
        return None

    modulus = int(modulus_match.group(1))
    numbers = [int(value) for value in re.findall(r"(?<![A-Za-z])\d+(?![A-Za-z])", text)]
    removed = False
    operands: list[int] = []
    for value in numbers:
        if not removed and value == modulus:
            removed = True
            continue
        operands.append(value)
    if len(operands) < 2:
        operands.extend([10, 3])
    return modulus, operands[0], operands[1]
