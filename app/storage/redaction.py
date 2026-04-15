from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)

PROVIDER_API_KEY_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
)

SAFE_KEY_NAMES = {
    "secret_redaction_summary",
}

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(sk|sk-or|sk-ant|ghp|github_pat)_[A-Za-z0-9_]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
)

_ENV_ASSIGNMENT_PATTERNS = tuple(
    re.compile(rf"(?i)\b{re.escape(name)}\s*=\s*([^\s,;]+)")
    for name in PROVIDER_API_KEY_ENV_NAMES
)


def redaction_summary() -> list[str]:
    """Human-readable summary of the built-in export redaction policy."""

    return [
        "Secret redaction is enabled for saved session JSON, trace JSONL, manifest, "
        "comparative-report, and bundle overview exports.",
        "Sensitive fields are redacted by key name before JSON snapshots are written.",
        "Provider API key environment names may be recorded as names, but their values are never exported.",
    ]


def redact_sensitive_data(value: Any) -> Any:
    """Recursively redact likely secrets from JSON-serializable data."""

    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    """Redact provider keys and bearer-like credentials inside text payloads."""

    redacted = value
    for pattern in _ENV_ASSIGNMENT_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(0).split("=")[0].rstrip() + "=" + REDACTED, redacted)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    if normalized in SAFE_KEY_NAMES:
        return False
    if normalized in SENSITIVE_KEY_FRAGMENTS:
        return True
    sensitive_suffixes = (
        "_api_key",
        "_apikey",
        "_authorization",
        "_bearer",
        "_credential",
        "_credentials",
        "_password",
        "_private_key",
        "_secret",
        "_token",
    )
    if normalized.endswith(sensitive_suffixes):
        return True
    return "private_key" in normalized or "api_key" in normalized
