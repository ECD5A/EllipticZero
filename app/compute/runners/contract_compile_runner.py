from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.compute.runners.toolchain_utils import (
    extract_semver,
    extract_solidity_pragma_spec,
    list_managed_solc_versions,
    resolve_explicit_binary_path,
    resolve_local_binary,
    resolve_managed_solc_binary,
    select_best_solc_version,
)


class ContractCompileRunner:
    """Run a bounded local Solidity compile check through solc or solcjs."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        managed_solc_dir: str = ".ellipticzero/tooling/solcx",
        managed_solc_version: str = "0.8.20",
        solc_binary: str = "solc",
        solcjs_binary: str = "solcjs",
        timeout_seconds: int = 12,
    ) -> None:
        self.enabled = enabled
        self.managed_solc_dir = managed_solc_dir
        self.managed_solc_version = managed_solc_version
        self.solc_binary = solc_binary
        self.solcjs_binary = solcjs_binary
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return self.enabled and self._resolve_binary() is not None

    def resolved_binary(self) -> str | None:
        return self._resolve_binary()

    def resolved_managed_binary(self) -> str | None:
        binary, _ = resolve_managed_solc_binary(
            managed_dir=self.managed_solc_dir,
            preferred_version=self.managed_solc_version,
        )
        return binary

    def resolved_managed_version(self) -> str | None:
        _, version = resolve_managed_solc_binary(
            managed_dir=self.managed_solc_dir,
            preferred_version=self.managed_solc_version,
        )
        return version

    def installed_managed_versions(self) -> list[str]:
        return list_managed_solc_versions(self.managed_solc_dir)

    def compiler_version(self) -> str | None:
        binary = self._resolve_binary()
        return self.compiler_version_for_binary(binary)

    def compiler_version_for_binary(self, binary: str | None) -> str | None:
        if binary is None:
            return None
        try:
            completed = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=min(self.timeout_seconds, 8),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        text = (completed.stdout or completed.stderr or "").strip()
        if not text:
            return None
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if "version:" in line.lower():
                return line
        for line in lines:
            if extract_semver(line):
                return line
        return None

    def run_compile(
        self,
        *,
        contract_code: str,
        language: str = "solidity",
        source_label: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The bounded smart-contract compile layer is disabled in the current configuration.",
                notes=["Enable local_research.smart_contract_compile_enabled to allow local compiler checks."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=None,
                    compiler_version=None,
                    pragma_spec=None,
                ),
            )
        if language.strip().lower() != "solidity":
            return self._result(
                status="invalid_input",
                conclusion="The current bounded compile adapter supports Solidity sources only.",
                notes=["Vyper sources remain available through parser, surface, and pattern-review tools."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=None,
                    compiler_version=None,
                    pragma_spec=None,
                ),
            )

        pragma_spec = extract_solidity_pragma_spec(contract_code)
        binary = self._resolve_binary(pragma_spec=pragma_spec, require_pragma_match=bool(pragma_spec))
        version = self.compiler_version_for_binary(binary)
        if binary is None:
            return self._result(
                status="unavailable",
                conclusion=(
                    "No local solc-compatible compiler matching the contract pragma was found for the bounded compile check."
                    if pragma_spec
                    else "No local solc-compatible compiler was found for the bounded compile check."
                ),
                notes=(
                    [
                        f"required_pragma={pragma_spec}",
                        "Install or provision a compatible solc version locally to enable pragma-aware compile checks.",
                        f"installed_managed_versions={', '.join(self.installed_managed_versions()) or 'none'}",
                    ]
                    if pragma_spec
                    else ["Install solc or solcjs locally to enable compile-path checks."]
                ),
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=None,
                    compiler_version=version,
                    pragma_spec=pragma_spec,
                ),
            )

        source_name = self._source_name(source_label)
        standard_json = {
            "language": "Solidity",
            "sources": {
                source_name: {
                    "content": contract_code,
                }
            },
            "settings": {
                "optimizer": {"enabled": False, "runs": 0},
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode.object"],
                        "": ["ast"],
                    }
                },
            },
        }

        try:
            completed = subprocess.run(
                [binary, "--standard-json"],
                input=json.dumps(standard_json),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._result(
                status="unavailable",
                conclusion="The bounded compiler check timed out before a result was produced.",
                notes=[f"compiler_timeout_seconds={self.timeout_seconds}"],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=binary,
                    compiler_version=version,
                    pragma_spec=pragma_spec,
                ),
            )
        except OSError as exc:
            return self._result(
                status="unavailable",
                conclusion="The local compiler binary could not be started for the bounded compile check.",
                notes=[str(exc)],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=binary,
                    compiler_version=version,
                    pragma_spec=pragma_spec,
                ),
            )

        payload = self._extract_json_payload(completed.stdout)
        diagnostics: list[dict[str, str]] = []
        contract_names: list[str] = []
        ast_present = False
        parse_error = None
        if payload is not None:
            diagnostics = self._normalize_diagnostics(payload.get("errors", []))
            contracts = payload.get("contracts", {})
            for source_contracts in contracts.values():
                if isinstance(source_contracts, dict):
                    contract_names.extend(str(name) for name in source_contracts.keys())
            ast_present = bool(
                any(
                    isinstance(source_data, dict) and source_data.get("ast")
                    for source_data in payload.get("sources", {}).values()
                )
            )
        else:
            parse_error = "compiler_output_not_json"

        error_count = sum(1 for item in diagnostics if item["severity"] == "error")
        warning_count = sum(1 for item in diagnostics if item["severity"] == "warning")
        notes: list[str] = []
        if completed.stderr.strip():
            notes.append(completed.stderr.strip())
        if parse_error:
            notes.append(parse_error)

        success = error_count == 0 and payload is not None
        status = "ok" if success else "observed_issue"
        conclusion = (
            "The bounded Solidity compile check completed locally."
            if success
            else "The bounded Solidity compile check surfaced errors or incomplete compiler output."
        )

        return self._result(
            status=status,
            conclusion=conclusion,
            notes=notes,
            result_data={
                **self._base_result_data(
                    language=language,
                    source_label=source_label,
                    compiler_binary=binary,
                    compiler_version=version,
                    pragma_spec=pragma_spec,
                ),
                "compile_succeeded": success,
                "return_code": completed.returncode,
                "error_count": error_count,
                "warning_count": warning_count,
                "diagnostics": diagnostics[:16],
                "compiled_contract_names": sorted(set(contract_names)),
                "compiled_contract_count": len(set(contract_names)),
                "ast_present": ast_present,
            },
        )

    def _resolve_binary(self, *, pragma_spec: str | None = None, require_pragma_match: bool = False) -> str | None:
        explicit_solc = resolve_explicit_binary_path(self.solc_binary)
        if explicit_solc is not None and self._binary_matches_pragma(explicit_solc, pragma_spec, require_pragma_match):
            return explicit_solc
        managed_binary, _ = resolve_managed_solc_binary(
            managed_dir=self.managed_solc_dir,
            preferred_version=self.managed_solc_version,
            pragma_spec=pragma_spec,
            require_pragma_match=require_pragma_match,
        )
        if managed_binary is not None:
            return managed_binary
        configured_solc = resolve_local_binary(self.solc_binary)
        if configured_solc is not None and self._binary_matches_pragma(configured_solc, pragma_spec, require_pragma_match):
            return configured_solc
        configured_solcjs = resolve_local_binary(self.solcjs_binary)
        if configured_solcjs is not None and self._binary_matches_pragma(configured_solcjs, pragma_spec, require_pragma_match):
            return configured_solcjs
        return None

    def _binary_matches_pragma(
        self,
        binary: str,
        pragma_spec: str | None,
        require_pragma_match: bool,
    ) -> bool:
        if not pragma_spec or not require_pragma_match:
            return True
        version_line = self.compiler_version_for_binary(binary)
        semver = extract_semver(version_line)
        if semver is None:
            return False
        selected = select_best_solc_version(
            installed_versions=[semver],
            preferred_version=semver,
            pragma_spec=pragma_spec,
            require_pragma_match=True,
        )
        return selected == semver

    def _source_name(self, source_label: str | None) -> str:
        if source_label:
            path = Path(source_label)
            return path.name or "Contract.sol"
        return "Contract.sol"

    def _extract_json_payload(self, stdout: str) -> dict[str, Any] | None:
        text = stdout.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                payload = json.loads(text[start : end + 1])
                return payload if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                return None

    def _normalize_diagnostics(self, items: Any) -> list[dict[str, str]]:
        diagnostics: list[dict[str, str]] = []
        if not isinstance(items, list):
            return diagnostics
        for item in items:
            if not isinstance(item, dict):
                continue
            diagnostics.append(
                {
                    "severity": str(item.get("severity", "info")).strip().lower(),
                    "type": str(item.get("type", "")).strip(),
                    "component": str(item.get("component", "")).strip(),
                    "message": str(item.get("formattedMessage") or item.get("message") or "").strip(),
                }
            )
        return diagnostics

    def _base_result_data(
        self,
        *,
        language: str,
        source_label: str | None,
        compiler_binary: str | None,
        compiler_version: str | None,
        pragma_spec: str | None,
    ) -> dict[str, Any]:
        return {
            "language": language,
            "source_label": source_label,
            "compiler_binary": compiler_binary,
            "compiler_version": compiler_version,
            "pragma_spec": pragma_spec,
        }

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
