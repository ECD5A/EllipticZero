# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

MAX_HOSTED_REQUEST_BYTES = 2_000_000
MAX_HOSTED_RESPONSE_BYTES = 4_000_000


def post_json(
    *,
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    encoded_payload = json.dumps(payload).encode("utf-8")
    if len(encoded_payload) > MAX_HOSTED_REQUEST_BYTES:
        raise RuntimeError(
            "Hosted provider request payload exceeds the bounded transport limit."
        )
    request = urllib_request.Request(
        url,
        data=encoded_payload,
        headers={"Content-Type": "application/json", **dict(headers)},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            raw_bytes = response.read(MAX_HOSTED_RESPONSE_BYTES + 1)
            if len(raw_bytes) > MAX_HOSTED_RESPONSE_BYTES:
                raise RuntimeError(
                    "Hosted provider response exceeds the bounded transport limit."
                )
            raw = raw_bytes.decode("utf-8")
    except urllib_error.HTTPError as exc:
        message = _decode_http_error(exc)
        raise RuntimeError(message) from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Hosted provider request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Hosted provider request timed out.") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Hosted provider returned non-JSON output.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Hosted provider returned an unexpected response shape.")
    if "error" in parsed:
        raise RuntimeError(_extract_error_message(parsed["error"]))
    return parsed


def _decode_http_error(exc: urllib_error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw)
    except Exception:
        payload = None
    if isinstance(payload, dict) and "error" in payload:
        return (
            f"Hosted provider request failed with HTTP {exc.code}: "
            f"{_extract_error_message(payload['error'])}"
        )
    return f"Hosted provider request failed with HTTP {exc.code}."


def _extract_error_message(error_payload: object) -> str:
    if isinstance(error_payload, dict):
        for key in ("message", "status", "code"):
            value = error_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(error_payload, str) and error_payload.strip():
        return error_payload.strip()
    return "Hosted provider request failed."
