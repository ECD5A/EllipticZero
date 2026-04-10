from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.compute.runners.toolchain_utils import (
    extract_semver,
    extract_solidity_pragma_spec,
    resolve_explicit_binary_path,
    resolve_local_binary,
    resolve_managed_solc_binary,
    select_best_solc_version,
)


class SlitherRunner:
    """Run a bounded Slither static analysis pass over a temporary Solidity source."""

    DEFAULT_DETECTORS = [
        "pragma",
        "solc-version",
        "reentrancy-eth",
        "reentrancy-no-eth",
        "low-level-calls",
        "unchecked-lowlevel",
        "tx-origin",
        "controlled-delegatecall",
        "calls-loop",
        "suicidal",
        "unprotected-upgrade",
    ]

    def __init__(
        self,
        *,
        enabled: bool = True,
        managed_solc_dir: str = ".ellipticzero/tooling/solcx",
        managed_solc_version: str = "0.8.20",
        slither_binary: str = "slither",
        solc_binary: str = "solc",
        timeout_seconds: int = 45,
        detectors: list[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self.managed_solc_dir = managed_solc_dir
        self.managed_solc_version = managed_solc_version
        self.slither_binary = slither_binary
        self.solc_binary = solc_binary
        self.timeout_seconds = timeout_seconds
        self.detectors = detectors or list(self.DEFAULT_DETECTORS)

    def is_available(self) -> bool:
        return self.enabled and self._resolve_binary() is not None and self._resolve_solc_binary() is not None

    def resolved_binary(self) -> str | None:
        return self._resolve_binary()

    def resolved_solc_binary(self) -> str | None:
        return self._resolve_solc_binary()

    def analyzer_version(self) -> str | None:
        return self.analyzer_version_for_binary(self._resolve_binary())

    def analyzer_version_for_binary(self, binary: str | None) -> str | None:
        if binary is None:
            return None
        try:
            completed = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=min(self.timeout_seconds, 10),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        text = (completed.stdout or completed.stderr or "").strip()
        return text.splitlines()[0].strip() if text else None

    def run_audit(
        self,
        *,
        contract_code: str,
        language: str = "solidity",
        source_label: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The bounded Slither analysis layer is disabled in the current configuration.",
                notes=["Enable local_research.slither_enabled to allow local Slither-based contract analysis."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                ),
            )
        if language.strip().lower() != "solidity":
            return self._result(
                status="invalid_input",
                conclusion="The current bounded Slither adapter supports Solidity sources only.",
                notes=["Vyper sources remain available through built-in parser, surface, and pattern-review tools."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                ),
            )

        pragma_spec = extract_solidity_pragma_spec(contract_code)
        binary = self._resolve_binary()
        version = self.analyzer_version_for_binary(binary)
        solc_binary = self._resolve_solc_binary(pragma_spec=pragma_spec, require_pragma_match=bool(pragma_spec))
        if binary is None:
            return self._result(
                status="unavailable",
                conclusion="No local Slither binary was found for the bounded static analyzer path.",
                notes=["Install slither-analyzer locally to enable Slither-based smart-contract analysis."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        if solc_binary is None:
            return self._result(
                status="unavailable",
                conclusion=(
                    "The bounded Slither path requires a local solc binary that matches the contract pragma."
                    if pragma_spec
                    else "The bounded Slither path requires a local solc binary for standalone Solidity source analysis."
                ),
                notes=(
                    [
                        f"required_pragma={pragma_spec}",
                        "Install or provision a compatible solc version locally before using Slither for pragma-aware analysis.",
                    ]
                    if pragma_spec
                    else ["Install a local solc binary or configure local_research.solc_binary before using Slither."]
                ),
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=None,
                    pragma_spec=pragma_spec,
                ),
            )

        source_name = self._source_name(source_label)
        detector_list = ",".join(self.detectors)

        temp_dir = self._create_workspace_temp_dir("ellipticzero_slither_")
        try:
            temp_path = temp_dir / source_name
            temp_path.write_text(contract_code, encoding="utf-8")
            completed = subprocess.run(
                [
                    binary,
                    str(temp_path),
                    "--json",
                    "-",
                    "--json-types",
                    "detectors",
                    "--fail-none",
                    "--disable-color",
                    "--solc",
                    solc_binary,
                    "--solc-working-dir",
                    str(temp_dir),
                    "--detect",
                    detector_list,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._result(
                status="unavailable",
                conclusion="The bounded Slither analysis timed out before detector results were produced.",
                notes=[f"slither_timeout_seconds={self.timeout_seconds}"],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        except OSError as exc:
            return self._result(
                status="unavailable",
                conclusion="The local Slither binary could not be started for the bounded static analyzer path.",
                notes=[str(exc)],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        payload = self._extract_json_payload(completed.stdout)
        findings: list[dict[str, str]] = []
        analysis_error: str | None = None
        if payload is not None:
            results = payload.get("results", {})
            if isinstance(results, dict):
                findings = self._normalize_findings(results.get("detectors", []))
            error_value = payload.get("error")
            if error_value:
                analysis_error = str(error_value).strip()
        else:
            analysis_error = "slither_output_not_json"

        detector_name_counts: dict[str, int] = {}
        impact_counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {}
        for finding in findings:
            check_name = finding["check"]
            detector_name_counts[check_name] = detector_name_counts.get(check_name, 0) + 1
            impact = finding["impact"]
            impact_counts[impact] = impact_counts.get(impact, 0) + 1
            confidence = finding["confidence"]
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

        notes: list[str] = []
        if completed.stderr.strip():
            notes.append(completed.stderr.strip())
        if analysis_error:
            notes.append(analysis_error)

        analysis_succeeded = payload is not None and analysis_error in {None, ""}
        finding_count = len(findings)
        if analysis_succeeded and finding_count == 0:
            status = "ok"
            conclusion = "The bounded Slither analysis completed locally without detector findings."
        elif finding_count > 0:
            status = "observed_issue"
            conclusion = "The bounded Slither analysis surfaced review-worthy detector findings."
        else:
            status = "observed_issue"
            conclusion = "The bounded Slither analysis did not produce a clean detector result."

        return self._result(
            status=status,
            conclusion=conclusion,
            notes=notes,
            result_data={
                **self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
                "analysis_succeeded": analysis_succeeded,
                "return_code": completed.returncode,
                "detector_selection": list(self.detectors),
                "finding_count": finding_count,
                "findings": findings[:24],
                "detector_name_counts": detector_name_counts,
                "impact_counts": impact_counts,
                "confidence_counts": confidence_counts,
                "high_severity_present": impact_counts.get("high", 0) > 0,
                "medium_severity_present": impact_counts.get("medium", 0) > 0,
            },
        )

    def _resolve_binary(self) -> str | None:
        return resolve_local_binary(self.slither_binary)

    def _resolve_solc_binary(self, *, pragma_spec: str | None = None, require_pragma_match: bool = False) -> str | None:
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
        return None

    def _source_name(self, source_label: str | None) -> str:
        if source_label:
            name = Path(source_label).name
            if name:
                sanitized = "".join("_" if char in '<>:"/\\|?*' else char for char in name).strip(" .")
                if sanitized:
                    return sanitized if sanitized.endswith(".sol") else f"{sanitized}.sol"
        return "Contract.sol"

    def _workspace_temp_root(self) -> Path:
        temp_root = Path(".ellipticzero") / "tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        return temp_root

    def _create_workspace_temp_dir(self, prefix: str) -> Path:
        temp_dir = self._workspace_temp_root() / f"{prefix}{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        return temp_dir

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

    def _normalize_findings(self, items: Any) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        if not isinstance(items, list):
            return findings
        for item in items:
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "check": str(item.get("check", "")).strip() or "unknown",
                    "impact": str(item.get("impact", "informational")).strip().lower(),
                    "confidence": str(item.get("confidence", "unknown")).strip().lower(),
                    "description": str(item.get("description", "")).strip(),
                }
            )
        return findings

    def _base_result_data(
        self,
        *,
        language: str,
        source_label: str | None,
        analyzer_binary: str | None,
        analyzer_version: str | None,
        solc_binary: str | None,
        pragma_spec: str | None,
    ) -> dict[str, Any]:
        return {
            "language": language,
            "source_label": source_label,
            "analyzer_binary": analyzer_binary,
            "analyzer_version": analyzer_version,
            "solc_binary": solc_binary,
            "pragma_spec": pragma_spec,
        }

    def _binary_matches_pragma(
        self,
        binary: str,
        pragma_spec: str | None,
        require_pragma_match: bool,
    ) -> bool:
        if not pragma_spec or not require_pragma_match:
            return True
        try:
            completed = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=min(self.timeout_seconds, 10),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        semver = extract_semver((completed.stdout or completed.stderr or "").strip())
        if semver is None:
            return False
        selected = select_best_solc_version(
            installed_versions=[semver],
            preferred_version=semver,
            pragma_spec=pragma_spec,
            require_pragma_match=True,
        )
        return selected == semver

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
