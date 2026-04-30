from __future__ import annotations

import json
import re
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
from app.tools.smart_contract_utils import build_contract_outline


class EchidnaRunner:
    """Run a bounded Echidna property or assertion pass on Solidity source."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        managed_solc_dir: str = ".ellipticzero/tooling/solcx",
        managed_solc_version: str = "0.8.20",
        echidna_binary: str = "echidna",
        solc_binary: str = "solc",
        timeout_seconds: int = 45,
        test_limit: int = 128,
        seq_len: int = 16,
    ) -> None:
        self.enabled = enabled
        self.managed_solc_dir = managed_solc_dir
        self.managed_solc_version = managed_solc_version
        self.echidna_binary = echidna_binary
        self.solc_binary = solc_binary
        self.timeout_seconds = timeout_seconds
        self.test_limit = test_limit
        self.seq_len = seq_len

    def is_available(self) -> bool:
        return self.enabled and self._resolve_binary() is not None and self._resolve_solc_binary() is not None

    def resolved_binary(self) -> str | None:
        return self._resolve_binary()

    def resolved_solc_binary(self) -> str | None:
        return self._resolve_solc_binary()

    def analyzer_version(self) -> str | None:
        binary = self._resolve_binary()
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
                conclusion="The bounded Echidna adapter is disabled in the current configuration.",
                notes=["Enable local_research.echidna_enabled to allow local Echidna-based contract fuzzing."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                    analysis_mode=None,
                    target_contract_name=None,
                    property_function_names=[],
                    assertion_surface_present=False,
                ),
            )
        if language.strip().lower() != "solidity":
            return self._result(
                status="invalid_input",
                conclusion="The current bounded Echidna adapter supports Solidity sources only.",
                notes=["Vyper sources remain available through built-in parser, surface, and pattern-review tools."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                    analysis_mode=None,
                    target_contract_name=None,
                    property_function_names=[],
                    assertion_surface_present=False,
                ),
            )

        outline = build_contract_outline(contract_code=contract_code, language="solidity")
        property_function_names = [
            item.name
            for item in outline.functions
            if item.kind == "function" and item.name.startswith("echidna_")
        ]
        assertion_surface_present = any(
            re.search(r"\bassert\s*\(", item.body)
            for item in outline.functions
        )
        analysis_mode = "property" if property_function_names else ("assertion" if assertion_surface_present else None)
        target_contract_name = self._select_target_contract_name(
            contract_names=outline.contract_names,
            property_function_names=property_function_names,
            assertion_surface_present=assertion_surface_present,
        )
        pragma_spec = extract_solidity_pragma_spec(contract_code)
        binary = self._resolve_binary()
        version = self.analyzer_version()
        solc_binary = self._resolve_solc_binary(pragma_spec=pragma_spec, require_pragma_match=bool(pragma_spec))

        if binary is None:
            return self._result(
                status="unavailable",
                conclusion="No local Echidna binary was found for the scoped smart-contract fuzzing path.",
                notes=["Install Echidna locally and expose the echidna binary to enable property-based contract fuzzing."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=None,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                    analysis_mode=analysis_mode,
                    target_contract_name=target_contract_name,
                    property_function_names=property_function_names,
                    assertion_surface_present=assertion_surface_present,
                ),
            )
        if solc_binary is None:
            return self._result(
                status="unavailable",
                conclusion=(
                    "The bounded Echidna path requires a local solc binary that matches the contract pragma."
                    if pragma_spec
                    else "The bounded Echidna path requires a local solc binary for standalone Solidity source analysis."
                ),
                notes=(
                    [
                        f"required_pragma={pragma_spec}",
                        "Install or provision a compatible solc version locally before using Echidna for pragma-aware analysis.",
                    ]
                    if pragma_spec
                    else ["Install a local solc binary or configure local_research.solc_binary before using Echidna."]
                ),
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=None,
                    pragma_spec=pragma_spec,
                    analysis_mode=analysis_mode,
                    target_contract_name=target_contract_name,
                    property_function_names=property_function_names,
                    assertion_surface_present=assertion_surface_present,
                ),
            )
        if analysis_mode is None or target_contract_name is None:
            return self._result(
                status="ok",
                conclusion="No Echidna property or assertion surface was found, so the bounded Echidna pass was skipped.",
                notes=[
                    "Add echidna_* property functions or Solidity assert() checks to make the contract applicable to the current bounded Echidna path.",
                ],
                result_data={
                    **self._base_result_data(
                        language=language,
                        source_label=source_label,
                        analyzer_binary=binary,
                        analyzer_version=version,
                        solc_binary=solc_binary,
                        pragma_spec=pragma_spec,
                        analysis_mode=None,
                        target_contract_name=None,
                        property_function_names=property_function_names,
                        assertion_surface_present=assertion_surface_present,
                    ),
                    "analysis_applicable": False,
                    "analysis_succeeded": False,
                    "return_code": 0,
                    "test_limit": self.test_limit,
                    "seq_len": self.seq_len,
                    "test_count": 0,
                    "passing_test_count": 0,
                    "failing_test_count": 0,
                    "unknown_test_count": 0,
                    "failing_tests": [],
                    "test_status_counts": {},
                    "tests": [],
                },
            )

        temp_dir = self._create_workspace_temp_dir("ellipticzero_echidna_")
        source_name = self._source_name(source_label)
        try:
            source_path = temp_dir / source_name
            config_path = temp_dir / "echidna.yaml"
            source_path.write_text(contract_code, encoding="utf-8")
            config_path.write_text(self._config_text(test_mode=analysis_mode), encoding="utf-8")
            completed = subprocess.run(
                [
                    binary,
                    str(source_path),
                    "--contract",
                    target_contract_name,
                    "--config",
                    str(config_path),
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
                conclusion="The bounded Echidna analysis timed out before property or assertion results were produced.",
                notes=[f"echidna_timeout_seconds={self.timeout_seconds}"],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                    analysis_mode=analysis_mode,
                    target_contract_name=target_contract_name,
                    property_function_names=property_function_names,
                    assertion_surface_present=assertion_surface_present,
                ),
            )
        except OSError as exc:
            return self._result(
                status="unavailable",
                conclusion="The local Echidna binary could not be started for the scoped smart-contract fuzzing path.",
                notes=[str(exc)],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    analyzer_binary=binary,
                    analyzer_version=version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                    analysis_mode=analysis_mode,
                    target_contract_name=target_contract_name,
                    property_function_names=property_function_names,
                    assertion_surface_present=assertion_surface_present,
                ),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        payload = self._extract_json_payload(completed.stdout)
        analysis_error: str | None = None
        if payload is not None:
            error_value = payload.get("error")
            if error_value:
                analysis_error = str(error_value).strip() or None
        elif completed.stdout.strip():
            analysis_error = "echidna_output_not_json"

        tests = self._normalize_tests(payload.get("tests") if isinstance(payload, dict) else None)
        test_status_counts: dict[str, int] = {}
        failing_tests: list[str] = []
        passing_test_count = 0
        failing_test_count = 0
        unknown_test_count = 0
        for item in tests:
            classification = item["classification"]
            test_status_counts[classification] = test_status_counts.get(classification, 0) + 1
            if classification == "passing":
                passing_test_count += 1
            elif classification == "failing":
                failing_test_count += 1
                failing_tests.append(item["name"])
            else:
                unknown_test_count += 1

        notes: list[str] = []
        if completed.stderr.strip():
            notes.append(completed.stderr.strip())
        if analysis_error:
            notes.append(analysis_error)

        analysis_succeeded = payload is not None and analysis_error in {None, ""}
        if failing_test_count > 0:
            status = "observed_issue"
            conclusion = "The bounded Echidna analysis surfaced failing property or assertion checks."
        elif analysis_succeeded and tests:
            status = "ok"
            conclusion = "The bounded Echidna analysis completed locally without failing property or assertion checks."
        elif analysis_succeeded:
            status = "ok"
            conclusion = "The bounded Echidna analysis completed, but no explicit property result required escalation."
        else:
            status = "observed_issue"
            conclusion = "The bounded Echidna analysis did not produce a clean property or assertion result."

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
                    analysis_mode=analysis_mode,
                    target_contract_name=target_contract_name,
                    property_function_names=property_function_names,
                    assertion_surface_present=assertion_surface_present,
                ),
                "analysis_applicable": True,
                "analysis_succeeded": analysis_succeeded,
                "return_code": completed.returncode,
                "test_limit": self.test_limit,
                "seq_len": self.seq_len,
                "test_count": len(tests),
                "passing_test_count": passing_test_count,
                "failing_test_count": failing_test_count,
                "unknown_test_count": unknown_test_count,
                "failing_tests": failing_tests[:12],
                "test_status_counts": test_status_counts,
                "tests": tests[:24],
            },
        )

    def _resolve_binary(self) -> str | None:
        explicit = resolve_explicit_binary_path(self.echidna_binary)
        if explicit is not None:
            return explicit
        return resolve_local_binary(self.echidna_binary)

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

    def _config_text(self, *, test_mode: str) -> str:
        return (
            f"testMode: {test_mode}\n"
            f"testLimit: {self.test_limit}\n"
            f"seqLen: {self.seq_len}\n"
            "format: json\n"
            "coverage: false\n"
        )

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
            pass
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if not stripped or stripped[0] not in "{[":
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            return payload if isinstance(payload, dict) else None
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None

    def _normalize_tests(self, raw_tests: Any) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        if isinstance(raw_tests, dict):
            items = []
            for name, value in raw_tests.items():
                if isinstance(value, dict):
                    items.append({"name": str(name), **value})
                else:
                    items.append({"name": str(name), "status": value})
        elif isinstance(raw_tests, list):
            items = raw_tests
        else:
            return normalized

        for item in items:
            if not isinstance(item, dict):
                continue
            name = (
                str(item.get("name", "")).strip()
                or str(item.get("property", "")).strip()
                or str(item.get("test", "")).strip()
                or str(item.get("contract", "")).strip()
                or "unknown"
            )
            raw_status = (
                str(item.get("status", "")).strip()
                or str(item.get("result", "")).strip()
                or str(item.get("state", "")).strip()
                or str(item.get("outcome", "")).strip()
                or "unknown"
            )
            classification = self._classify_test_status(raw_status)
            normalized.append(
                {
                    "name": name,
                    "status": raw_status,
                    "classification": classification,
                }
            )
        return normalized

    def _classify_test_status(self, raw_status: str) -> str:
        lowered = raw_status.strip().lower()
        if any(token in lowered for token in ("passed", "pass", "success", "ok", "true")):
            return "passing"
        if any(token in lowered for token in ("violat", "falsif", "fail", "error", "false", "shrunk", "solved")):
            return "failing"
        return "unknown"

    def _select_target_contract_name(
        self,
        *,
        contract_names: list[str],
        property_function_names: list[str],
        assertion_surface_present: bool,
    ) -> str | None:
        if not contract_names:
            return None
        if property_function_names or assertion_surface_present:
            return contract_names[-1]
        return contract_names[0]

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

    def _base_result_data(
        self,
        *,
        language: str,
        source_label: str | None,
        analyzer_binary: str | None,
        analyzer_version: str | None,
        solc_binary: str | None,
        pragma_spec: str | None,
        analysis_mode: str | None,
        target_contract_name: str | None,
        property_function_names: list[str],
        assertion_surface_present: bool,
    ) -> dict[str, Any]:
        return {
            "language": language,
            "source_label": source_label,
            "analyzer_binary": analyzer_binary,
            "analyzer_version": analyzer_version,
            "solc_binary": solc_binary,
            "pragma_spec": pragma_spec,
            "analysis_mode": analysis_mode,
            "target_contract_name": target_contract_name,
            "property_function_names": property_function_names,
            "property_count": len(property_function_names),
            "assertion_surface_present": assertion_surface_present,
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
