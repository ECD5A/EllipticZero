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


class FoundryRunner:
    """Run a bounded Forge build/inspect pass over a temporary Solidity source."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        managed_solc_dir: str = ".ellipticzero/tooling/solcx",
        managed_solc_version: str = "0.8.20",
        forge_binary: str = "forge",
        solc_binary: str = "solc",
        timeout_seconds: int = 45,
    ) -> None:
        self.enabled = enabled
        self.managed_solc_dir = managed_solc_dir
        self.managed_solc_version = managed_solc_version
        self.forge_binary = forge_binary
        self.solc_binary = solc_binary
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return self.enabled and self._resolve_binary() is not None and self._resolve_solc_binary() is not None

    def resolved_binary(self) -> str | None:
        return self._resolve_binary()

    def resolved_solc_binary(self) -> str | None:
        return self._resolve_solc_binary()

    def forge_version(self) -> str | None:
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
        contract_root: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The bounded Foundry adapter is disabled in the current configuration.",
                notes=["Enable local_research.foundry_enabled to allow local Forge-based contract inspection."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=None,
                    forge_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                ),
            )
        if language.strip().lower() != "solidity":
            return self._result(
                status="invalid_input",
                conclusion="The current bounded Foundry adapter supports Solidity sources only.",
                notes=["Vyper sources remain available through built-in parser, surface, and pattern-review tools."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=None,
                    forge_version=None,
                    solc_binary=None,
                    pragma_spec=None,
                ),
            )

        pragma_spec = extract_solidity_pragma_spec(contract_code)
        forge_binary = self._resolve_binary()
        forge_version = self.forge_version()
        solc_binary = self._resolve_solc_binary(pragma_spec=pragma_spec, require_pragma_match=bool(pragma_spec))
        if forge_binary is None:
            return self._result(
                status="unavailable",
                conclusion="No local Forge binary was found for the bounded Foundry adapter.",
                notes=["Install Foundry locally and ensure the forge binary is available in the project environment."],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=None,
                    forge_version=forge_version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        if solc_binary is None:
            return self._result(
                status="unavailable",
                conclusion=(
                    "The bounded Foundry path requires a local solc binary that matches the contract pragma."
                    if pragma_spec
                    else "The bounded Foundry path requires a local solc binary for standalone Solidity source analysis."
                ),
                notes=(
                    [
                        f"required_pragma={pragma_spec}",
                        "Install or provision a compatible solc version locally before using Foundry for pragma-aware analysis.",
                    ]
                    if pragma_spec
                    else ["Install a local solc binary or configure local_research.solc_binary before using Foundry."]
                ),
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=forge_binary,
                    forge_version=forge_version,
                    solc_binary=None,
                    pragma_spec=pragma_spec,
                ),
            )

        outline = build_contract_outline(contract_code=contract_code, language="solidity")
        contract_names = outline.contract_names[:4]
        project_root = self._resolve_project_root(contract_root)
        project_mode = project_root is not None
        root = project_root or self._create_workspace_temp_dir("ellipticzero_foundry_")
        temp_root = None if project_mode else root
        tests_succeeded: bool | None = None
        test_return_code: int | None = None
        failing_tests: list[str] = []
        test_output_summary: list[str] = []

        try:
            if not project_mode:
                src_dir = root / "src"
                src_dir.mkdir(parents=True, exist_ok=True)
                source_name = self._source_name(source_label)
                source_path = src_dir / source_name
                source_path.write_text(contract_code, encoding="utf-8")
                (root / "foundry.toml").write_text(
                    '[profile.default]\nsrc = "src"\nout = "out"\nlibs = []\ncache_path = "cache"\n',
                    encoding="utf-8",
                )
            build_completed = subprocess.run(
                self._build_command(
                    binary=forge_binary,
                    root=root,
                    solc_binary=solc_binary,
                ),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
            if build_completed.returncode != 0:
                notes = []
                if build_completed.stderr.strip():
                    notes.append(build_completed.stderr.strip())
                if build_completed.stdout.strip():
                    notes.append(build_completed.stdout.strip())
                return self._result(
                    status="observed_issue",
                    conclusion="The bounded Foundry build surfaced project-level issues or could not complete cleanly.",
                    notes=notes[:4],
                    result_data={
                        **self._base_result_data(
                            language=language,
                            source_label=source_label,
                            forge_binary=forge_binary,
                            forge_version=forge_version,
                            solc_binary=solc_binary,
                            pragma_spec=pragma_spec,
                        ),
                        "build_succeeded": False,
                        "return_code": build_completed.returncode,
                        "contract_names": contract_names,
                        "inspect_contracts_attempted": 0,
                        "inspect_contracts_succeeded": 0,
                        "method_identifier_counts": {},
                        "storage_entry_counts": {},
                        "storage_layout_present": False,
                        "project_mode": project_mode,
                        "foundry_toml_present": project_mode,
                        "contract_root": str(root) if project_mode else contract_root,
                        "test_return_code": test_return_code,
                        "tests_succeeded": tests_succeeded,
                        "failing_tests": failing_tests,
                        "test_output_summary": test_output_summary,
                    },
                )

            method_identifier_counts: dict[str, int] = {}
            storage_entry_counts: dict[str, int] = {}
            notes: list[str] = []
            inspect_contracts_succeeded = 0

            if project_mode:
                test_completed = subprocess.run(
                    self._test_command(
                        binary=forge_binary,
                        root=root,
                        solc_binary=solc_binary,
                    ),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_seconds,
                    check=False,
                )
                test_return_code = test_completed.returncode
                tests_succeeded = test_completed.returncode == 0
                combined_test_output = "\n".join(
                    value for value in (test_completed.stdout, test_completed.stderr) if value
                )
                failing_tests = self._extract_failing_tests(combined_test_output)
                test_output_summary = self._summarize_process_output(combined_test_output)
                if test_completed.returncode != 0 and not failing_tests:
                    notes.extend(test_output_summary[:2])

            for contract_name in contract_names:
                methods_payload = self._run_inspect(
                    forge_binary=forge_binary,
                    root=root,
                    solc_binary=solc_binary,
                    contract_name=contract_name,
                    field_name="methodIdentifiers",
                )
                storage_payload = self._run_inspect(
                    forge_binary=forge_binary,
                    root=root,
                    solc_binary=solc_binary,
                    contract_name=contract_name,
                    field_name="storageLayout",
                )
                methods_data = self._extract_json_payload(methods_payload.stdout)
                storage_data = self._extract_json_payload(storage_payload.stdout)
                if methods_data is not None or storage_data is not None:
                    inspect_contracts_succeeded += 1
                if isinstance(methods_data, dict):
                    method_identifier_counts[contract_name] = len(methods_data)
                elif methods_payload.stderr.strip():
                    notes.append(f"{contract_name}:methodIdentifiers:{methods_payload.stderr.strip()}")
                if isinstance(storage_data, dict):
                    storage_entries = storage_data.get("storage")
                    if isinstance(storage_entries, list):
                        storage_entry_counts[contract_name] = len(storage_entries)
                    else:
                        storage_entry_counts[contract_name] = 0
                elif storage_payload.stderr.strip():
                    notes.append(f"{contract_name}:storageLayout:{storage_payload.stderr.strip()}")
        except subprocess.TimeoutExpired:
            return self._result(
                status="unavailable",
                conclusion="The bounded Foundry analysis timed out before build and inspection completed.",
                notes=[f"foundry_timeout_seconds={self.timeout_seconds}"],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=forge_binary,
                    forge_version=forge_version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        except OSError as exc:
            return self._result(
                status="unavailable",
                conclusion="The local Forge binary could not be started for the bounded Foundry adapter.",
                notes=[str(exc)],
                result_data=self._base_result_data(
                    language=language,
                    source_label=source_label,
                    forge_binary=forge_binary,
                    forge_version=forge_version,
                    solc_binary=solc_binary,
                    pragma_spec=pragma_spec,
                ),
            )
        finally:
            if temp_root is not None:
                shutil.rmtree(temp_root, ignore_errors=True)

        storage_layout_present = any(count > 0 for count in storage_entry_counts.values())
        result_data = {
            **self._base_result_data(
                language=language,
                source_label=source_label,
                forge_binary=forge_binary,
                forge_version=forge_version,
                solc_binary=solc_binary,
                pragma_spec=pragma_spec,
            ),
            "build_succeeded": True,
            "return_code": 0,
            "contract_names": contract_names,
            "inspect_contracts_attempted": len(contract_names),
            "inspect_contracts_succeeded": inspect_contracts_succeeded,
            "method_identifier_counts": method_identifier_counts,
            "storage_entry_counts": storage_entry_counts,
            "storage_layout_present": storage_layout_present,
            "project_mode": project_mode,
            "foundry_toml_present": project_mode,
            "contract_root": str(root) if project_mode else contract_root,
            "test_return_code": test_return_code,
            "tests_succeeded": tests_succeeded,
            "failing_tests": failing_tests,
            "test_output_summary": test_output_summary,
        }
        if tests_succeeded is False:
            return self._result(
                status="observed_issue",
                conclusion="The bounded Foundry project build completed, but Forge tests surfaced failing checks.",
                notes=notes[:6],
                result_data=result_data,
            )
        if inspect_contracts_succeeded == 0 and contract_names:
            return self._result(
                status="observed_issue",
                conclusion="The bounded Foundry build completed, but contract inspection did not return a clean structural result.",
                notes=notes[:6],
                result_data=result_data,
            )
        return self._result(
            status="ok",
            conclusion="The bounded Foundry adapter completed a local build and structural contract inspection.",
            notes=notes[:6],
            result_data=result_data,
        )

    def _resolve_binary(self) -> str | None:
        explicit = resolve_explicit_binary_path(self.forge_binary)
        if explicit is not None:
            return explicit
        return resolve_local_binary(self.forge_binary)

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

    def _build_command(self, *, binary: str, root: Path, solc_binary: str) -> list[str]:
        return [
            binary,
            "build",
            "--root",
            str(root),
            "--offline",
            "--force",
            "--use",
            solc_binary,
        ]

    def _test_command(self, *, binary: str, root: Path, solc_binary: str) -> list[str]:
        return [
            binary,
            "test",
            "--root",
            str(root),
            "--offline",
            "--use",
            solc_binary,
        ]

    def _resolve_project_root(self, contract_root: str | None) -> Path | None:
        if not contract_root:
            return None
        try:
            root = Path(contract_root).expanduser().resolve()
        except OSError:
            return None
        if root.is_file():
            root = root.parent
        if not root.is_dir():
            return None
        if not (root / "foundry.toml").is_file():
            return None
        return root

    def _summarize_process_output(self, output: str) -> list[str]:
        lines = [" ".join(line.strip().split()) for line in output.splitlines()]
        meaningful = [line for line in lines if line]
        return meaningful[:8]

    def _extract_failing_tests(self, output: str) -> list[str]:
        failing: list[str] = []
        for line in output.splitlines():
            lowered = line.lower()
            if "[fail" not in lowered and "fail:" not in lowered and "failing" not in lowered:
                continue
            for match in re.findall(r"\btest[A-Za-z0-9_]*(?:\([^)]*\))?", line):
                if match not in failing:
                    failing.append(match)
            if not failing:
                cleaned = " ".join(line.strip().split())
                if cleaned and cleaned not in failing:
                    failing.append(cleaned[:180])
        return failing[:12]

    def _run_inspect(
        self,
        *,
        forge_binary: str,
        root: Path,
        solc_binary: str,
        contract_name: str,
        field_name: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                forge_binary,
                "inspect",
                contract_name,
                field_name,
                "--root",
                str(root),
                "--offline",
                "--use",
                solc_binary,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout_seconds,
            check=False,
        )

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

    def _source_name(self, source_label: str | None) -> str:
        if source_label:
            name = Path(source_label).name
            if name:
                return name if name.endswith(".sol") else f"{name}.sol"
        return "Contract.sol"

    def _workspace_temp_root(self) -> Path:
        temp_root = Path(".ellipticzero") / "tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        return temp_root

    def _create_workspace_temp_dir(self, prefix: str) -> Path:
        temp_dir = self._workspace_temp_root() / f"{prefix}{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        return temp_dir

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
        forge_binary: str | None,
        forge_version: str | None,
        solc_binary: str | None,
        pragma_spec: str | None,
    ) -> dict[str, Any]:
        return {
            "language": language,
            "source_label": source_label,
            "forge_binary": forge_binary,
            "forge_version": forge_version,
            "solc_binary": solc_binary,
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
