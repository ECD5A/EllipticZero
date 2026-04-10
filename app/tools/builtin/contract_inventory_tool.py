from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from os.path import normpath
from pathlib import Path
from typing import Any

from app.models.tool_payloads import SmartContractInventoryPayload
from app.tools.base import BaseTool

_IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".ellipticzero",
    "cache",
    "artifacts",
    "out",
    "build",
    "dist",
}

_DEPENDENCY_DIRECTORIES = {
    "node_modules",
    "lib",
    "vendor",
}


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


class ContractInventoryTool(BaseTool):
    """Build a bounded inventory of local Solidity/Vyper sources inside a repo or contract root."""

    name = "contract_inventory_tool"
    category = "smart_contract_audit"
    description = "Scan a local contract root and summarize bounded repository inventory, scope, and candidate review files."
    version = "0.1.0"
    input_schema_hint = "SmartContractInventoryPayload"
    output_schema_hint = "Bounded contract repository inventory"
    payload_model = SmartContractInventoryPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        root_path = Path(str(payload.get("root_path", ""))).expanduser()
        max_files = int(payload.get("max_files", 64) or 64)
        if not root_path.exists() or not root_path.is_dir():
            return self.make_result(
                status="invalid_input",
                conclusion="The provided contract root does not exist or is not a directory.",
                notes=["Provide a readable local directory containing Solidity or Vyper sources."],
                result_data={
                    "recognized": False,
                    "root_path": str(root_path),
                    "file_count": 0,
                    "first_party_file_count": 0,
                    "dependency_file_count": 0,
                    "solidity_file_count": 0,
                    "vyper_file_count": 0,
                    "scanned_files": [],
                    "candidate_files": [],
                    "dependency_candidate_files": [],
                    "pragma_summary": [],
                    "largest_files": [],
                    "contract_units": [],
                    "entrypoint_candidates": [],
                    "first_party_entrypoint_candidates": [],
                    "shared_dependency_files": [],
                    "import_graph_summary": [],
                    "entrypoint_flow_summaries": [],
                    "entrypoint_review_lanes": [],
                    "risk_family_lane_summaries": [],
                    "entrypoint_function_family_priorities": [],
                    "risk_linked_files": [],
                    "dependency_review_files": [],
                    "first_party_dependency_edges": 0,
                    "scope_summary": [],
                    "issues": [],
                },
            )

        discovered_files: list[Path] = []
        dependency_dirs_present = sorted(
            path.name for path in root_path.iterdir() if path.is_dir() and path.name in {"lib", "vendor", "node_modules"}
        )
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _IGNORED_DIRECTORIES for part in path.parts):
                continue
            if path.suffix.lower() not in {".sol", ".vy"}:
                continue
            discovered_files.append(path)
            if len(discovered_files) >= max_files:
                break

        solidity_files = [path for path in discovered_files if path.suffix.lower() == ".sol"]
        vyper_files = [path for path in discovered_files if path.suffix.lower() == ".vy"]
        contract_units: list[str] = []
        pragma_counter: Counter[str] = Counter()
        candidate_scores: list[tuple[int, str]] = []
        file_line_counts: list[tuple[int, str]] = []
        unreadable_files: list[str] = []
        readable_text_by_file: dict[str, str] = {}
        risk_markers_by_file: dict[str, list[str]] = {}
        function_family_markers_by_file: dict[str, list[str]] = {}

        for path in discovered_files:
            relative_label = self._relative_label(root_path, path)
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    text = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    unreadable_files.append(relative_label)
                    continue
            except OSError:
                unreadable_files.append(relative_label)
                continue

            readable_text_by_file[relative_label] = text
            risk_markers_by_file[relative_label] = self._risk_markers(text)
            function_family_markers_by_file[relative_label] = self._function_family_markers(text)
            pragma = self._extract_pragma(text)
            if pragma:
                pragma_counter[pragma] += 1
            contract_units.extend(self._extract_contract_units(text))
            candidate_scores.append((self._candidate_score(relative_label, text), relative_label))
            file_line_counts.append((text.count("\n") + 1, relative_label))

        discovered_labels = [self._relative_label(root_path, path) for path in discovered_files]
        first_party_labels = [
            label for label in discovered_labels if not self._is_dependency_label(label)
        ]
        dependency_labels = [
            label for label in discovered_labels if self._is_dependency_label(label)
        ]
        local_import_targets: dict[str, list[str]] = {}
        imported_by_counter: Counter[str] = Counter()
        first_party_dependency_edges = 0
        for relative_label, text in readable_text_by_file.items():
            resolved_targets = self._resolve_local_import_targets(
                relative_label=relative_label,
                raw_imports=self._extract_imports(text),
                discovered_labels=discovered_labels,
            )
            local_import_targets[relative_label] = resolved_targets
            for target in resolved_targets:
                imported_by_counter[target] += 1
                if (
                    not self._is_dependency_label(relative_label)
                    and self._is_dependency_label(target)
                ):
                    first_party_dependency_edges += 1

        contract_units = list(dict.fromkeys(contract_units))
        candidate_score_map = {label: score for score, label in candidate_scores}
        candidate_files = [
            label
            for score, label in sorted(candidate_scores, key=lambda item: (-item[0], item[1]))
            if score > 0 and label in first_party_labels
        ][:8]
        dependency_candidate_files = [
            label
            for score, label in sorted(candidate_scores, key=lambda item: (-item[0], item[1]))
            if score > 0 and label in dependency_labels
        ][:6]
        largest_files = [
            f"{label} ({line_count} lines)"
            for line_count, label in sorted(file_line_counts, key=lambda item: (-item[0], item[1]))[:6]
        ]
        pragma_summary = [
            f"{pragma} x{count}"
            for pragma, count in pragma_counter.most_common(8)
        ]
        scanned_files = [self._relative_label(root_path, path) for path in discovered_files[:16]]
        entrypoint_candidates = self._build_entrypoint_candidates(
            discovered_labels=first_party_labels,
            local_import_targets=local_import_targets,
            imported_by_counter=imported_by_counter,
            candidate_score_map=candidate_score_map,
            readable_text_by_file=readable_text_by_file,
        )
        risk_linked_files = self._build_risk_linked_files(
            discovered_labels=discovered_labels,
            readable_text_by_file=readable_text_by_file,
            candidate_score_map=candidate_score_map,
        )
        shared_dependency_files = [
            f"{label} (imported by {count})"
            for label, count in imported_by_counter.most_common(6)
            if count >= 2
        ]
        dependency_review_files = [
            item
            for item in risk_linked_files
            if self._is_dependency_label(item.split(" [", 1)[0])
        ][:6]
        entrypoint_flow_summaries = self._build_entrypoint_flow_summaries(
            entrypoint_candidates=entrypoint_candidates,
            local_import_targets=local_import_targets,
            risk_linked_files=risk_linked_files,
        )
        entrypoint_review_lanes = self._build_entrypoint_review_lanes(
            entrypoint_candidates=entrypoint_candidates,
            local_import_targets=local_import_targets,
            risk_markers_by_file=risk_markers_by_file,
        )
        risk_family_lane_summaries = self._build_risk_family_lane_summaries(
            entrypoint_candidates=entrypoint_candidates,
            local_import_targets=local_import_targets,
            risk_markers_by_file=risk_markers_by_file,
        )
        entrypoint_function_family_priorities = self._build_entrypoint_function_family_priorities(
            entrypoint_candidates=entrypoint_candidates,
            local_import_targets=local_import_targets,
            function_family_markers_by_file=function_family_markers_by_file,
        )
        import_edge_count = sum(len(targets) for targets in local_import_targets.values())
        dependency_import_edge_count = sum(
            len(local_import_targets.get(label, [])) for label in dependency_labels
        )
        import_graph_summary: list[str] = []
        if import_edge_count:
            import_graph_summary.append(f"local import edges={import_edge_count}")
        import_graph_summary.append(
            f"scope split=first-party:{len(first_party_labels)} dependency:{len(dependency_labels)}"
        )
        if first_party_dependency_edges:
            import_graph_summary.append(f"first-party -> dependency edges={first_party_dependency_edges}")
        if dependency_import_edge_count:
            import_graph_summary.append(f"dependency import edges={dependency_import_edge_count}")
        if entrypoint_candidates:
            import_graph_summary.append(f"entrypoints={', '.join(entrypoint_candidates[:4])}")
        if shared_dependency_files:
            import_graph_summary.append(f"shared dependencies={', '.join(shared_dependency_files[:3])}")
        if entrypoint_flow_summaries:
            import_graph_summary.append(f"entrypoint flows={len(entrypoint_flow_summaries)}")
        if entrypoint_review_lanes:
            import_graph_summary.append(f"review lanes={len(entrypoint_review_lanes)}")
        if risk_family_lane_summaries:
            import_graph_summary.append(f"risk family lanes={len(risk_family_lane_summaries)}")
        if entrypoint_function_family_priorities:
            import_graph_summary.append(f"function family priorities={len(entrypoint_function_family_priorities)}")

        issues: list[str] = []
        if len(first_party_labels) >= 8:
            issues.append("multi_file_repo_surface_present")
        if len(discovered_files) >= max_files:
            issues.append("inventory_scan_truncated")
        if solidity_files and vyper_files:
            issues.append("mixed_language_repo_present")
        if dependency_dirs_present:
            issues.append("dependency_contract_dirs_present")
        if dependency_labels:
            issues.append("dependency_contract_files_present")
        if unreadable_files:
            issues.append("unreadable_contract_files_present")
        if import_edge_count > 0:
            issues.append("repo_local_import_graph_present")
        if first_party_dependency_edges > 0:
            issues.append("first_party_dependency_edges_present")
        if len(entrypoint_candidates) > 1:
            issues.append("multiple_entrypoint_candidates_present")
        if shared_dependency_files:
            issues.append("shared_dependency_hub_present")
        if entrypoint_flow_summaries:
            issues.append("entrypoint_dependency_flow_present")
        if entrypoint_review_lanes:
            issues.append("entrypoint_risk_lane_present")
        if risk_family_lane_summaries:
            issues.append("entrypoint_risk_family_lane_present")
        if entrypoint_function_family_priorities:
            issues.append("entrypoint_function_family_priority_present")
        if risk_linked_files:
            issues.append("repo_risk_linked_files_present")
        if dependency_review_files:
            issues.append("dependency_review_surface_present")

        notes = ["This inventory is bounded and scope-oriented; it does not imply vulnerability coverage."]
        if dependency_dirs_present:
            notes.append(
                "Dependency-style directories were present and may require separate manual scoping: "
                + ", ".join(dependency_dirs_present)
                + "."
            )
        if dependency_labels:
            notes.append(
                "First-party files were prioritized for candidate review and entrypoints while imported dependency code stayed visible as bounded dependency scope."
            )

        scope_summary = [
            f"first-party files={len(first_party_labels)}",
            f"dependency files={len(dependency_labels)}",
        ]
        if first_party_dependency_edges:
            scope_summary.append(f"first-party dependency edges={first_party_dependency_edges}")
        if dependency_review_files:
            scope_summary.append(f"dependency review files={len(dependency_review_files)}")

        recognized = bool(discovered_files)
        return self.make_result(
            status="ok" if recognized else "observed_issue",
            conclusion=(
                "Local contract repository inventory was built for bounded scoping and review prioritization."
                if recognized
                else "No Solidity or Vyper sources were discovered under the provided contract root."
            ),
            notes=notes,
            result_data={
                "recognized": recognized,
                "root_path": str(root_path),
                "file_count": len(discovered_files),
                "first_party_file_count": len(first_party_labels),
                "dependency_file_count": len(dependency_labels),
                "solidity_file_count": len(solidity_files),
                "vyper_file_count": len(vyper_files),
                "scanned_files": scanned_files,
                "candidate_files": candidate_files,
                "dependency_candidate_files": dependency_candidate_files,
                "pragma_summary": pragma_summary,
                "largest_files": largest_files,
                "contract_units": contract_units[:12],
                "entrypoint_candidates": entrypoint_candidates,
                "first_party_entrypoint_candidates": entrypoint_candidates,
                "shared_dependency_files": shared_dependency_files,
                "import_graph_summary": import_graph_summary,
                "entrypoint_flow_summaries": entrypoint_flow_summaries,
                "entrypoint_review_lanes": entrypoint_review_lanes,
                "risk_family_lane_summaries": risk_family_lane_summaries,
                "entrypoint_function_family_priorities": entrypoint_function_family_priorities,
                "risk_linked_files": risk_linked_files,
                "dependency_review_files": dependency_review_files,
                "first_party_dependency_edges": first_party_dependency_edges,
                "scope_summary": scope_summary,
                "dependency_dirs_present": dependency_dirs_present,
                "unreadable_files": unreadable_files[:8],
                "issues": issues,
            },
        )

    @staticmethod
    def _relative_label(root_path: Path, path: Path) -> str:
        try:
            return str(path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            return str(path)

    @staticmethod
    def _is_dependency_label(relative_label: str) -> bool:
        return any(part in _DEPENDENCY_DIRECTORIES for part in Path(relative_label).parts)

    @staticmethod
    def _extract_pragma(text: str) -> str | None:
        match = re.search(r"\bpragma\s+solidity\s+([^;]+);", text, flags=re.IGNORECASE)
        if match is not None:
            return "solidity " + match.group(1).strip()
        match = re.search(r"#\s*@version\s+([^\n]+)", text, flags=re.IGNORECASE)
        if match is not None:
            return "vyper " + match.group(1).strip()
        return None

    @staticmethod
    def _extract_contract_units(text: str) -> list[str]:
        names = re.findall(
            r"\b(?:contract|interface|library)\s+([A-Za-z_][A-Za-z0-9_]*)",
            text,
            flags=re.IGNORECASE,
        )
        return [name.strip() for name in names if name.strip()]

    @staticmethod
    def _extract_imports(text: str) -> list[str]:
        solidity_imports = re.findall(
            r"""\bimport\s+(?:[^;]*?\s+from\s+)?["']([^"']+)["']\s*;""",
            text,
            flags=re.IGNORECASE,
        )
        vyper_imports = re.findall(
            r"""\bfrom\s+([A-Za-z0-9_./]+)\s+import\s+[A-Za-z0-9_,\s*]+""",
            text,
            flags=re.IGNORECASE,
        )
        imports = [item.strip() for item in [*solidity_imports, *vyper_imports] if item.strip()]
        return list(dict.fromkeys(imports))

    @staticmethod
    def _resolve_local_import_targets(
        *,
        relative_label: str,
        raw_imports: list[str],
        discovered_labels: list[str],
    ) -> list[str]:
        discovered_set = set(discovered_labels)
        resolved: list[str] = []
        current_parent = Path(relative_label).parent

        for raw_import in raw_imports:
            normalized = raw_import.replace("\\", "/").strip()
            candidates: list[str] = []
            if normalized.startswith("."):
                direct = normpath(str(current_parent / normalized)).replace("\\", "/")
                candidates.extend([direct, f"{direct}.sol", f"{direct}.vy"])
            else:
                candidates.extend(
                    [
                        normalized,
                        normalized.lstrip("./"),
                        f"node_modules/{normalized}",
                        f"lib/{normalized}",
                        f"vendor/{normalized}",
                        f"{normalized}.sol",
                        f"{normalized}.vy",
                        f"node_modules/{normalized}.sol",
                        f"node_modules/{normalized}.vy",
                        f"lib/{normalized}.sol",
                        f"lib/{normalized}.vy",
                        f"vendor/{normalized}.sol",
                        f"vendor/{normalized}.vy",
                    ]
                )
                suffix_matches = [label for label in discovered_labels if label.endswith(normalized)]
                if len(suffix_matches) == 1:
                    candidates.append(suffix_matches[0])
            target = next((candidate for candidate in candidates if candidate in discovered_set), None)
            if target and target != relative_label:
                resolved.append(target)
        return list(dict.fromkeys(resolved))

    @classmethod
    def _build_entrypoint_candidates(
        cls,
        *,
        discovered_labels: list[str],
        local_import_targets: dict[str, list[str]],
        imported_by_counter: Counter[str],
        candidate_score_map: Mapping[str, int],
        readable_text_by_file: Mapping[str, str],
    ) -> list[str]:
        ranked: list[tuple[int, str]] = []
        root_ranked: list[tuple[int, str]] = []
        for label in discovered_labels:
            unit_count = len(cls._extract_contract_units(readable_text_by_file.get(label, "")))
            import_count = len(local_import_targets.get(label, []))
            imported_by = int(imported_by_counter.get(label, 0) or 0)
            score = int(candidate_score_map.get(label, 0)) + unit_count + (import_count * 2)
            if score <= 0:
                continue
            ranked_item = (score, label)
            ranked.append(ranked_item)
            if imported_by == 0:
                root_ranked.append((score + 2, label))
        if root_ranked:
            root_ranked.sort(key=lambda item: (-item[0], item[1]))
            return [label for _, label in root_ranked[:6]]
        if not ranked:
            return []
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [label for _, label in ranked[:6]]

    @staticmethod
    def _build_risk_linked_files(
        *,
        discovered_labels: list[str],
        readable_text_by_file: Mapping[str, str],
        candidate_score_map: Mapping[str, int],
    ) -> list[str]:
        ranked: list[tuple[int, str]] = []
        for label in discovered_labels:
            markers = ContractInventoryTool._risk_markers(readable_text_by_file.get(label, ""))
            if not markers:
                continue
            score = len(markers) + int(candidate_score_map.get(label, 0))
            ranked.append((score, f"{label} [{', '.join(markers[:4])}]"))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [label for _, label in ranked[:8]]

    @staticmethod
    def _build_entrypoint_flow_summaries(
        *,
        entrypoint_candidates: list[str],
        local_import_targets: Mapping[str, list[str]],
        risk_linked_files: list[str],
    ) -> list[str]:
        risk_labels = {item.split(" [", 1)[0] for item in risk_linked_files}
        flows: list[str] = []
        for entrypoint in entrypoint_candidates[:4]:
            visited: set[str] = {entrypoint}
            queue: list[tuple[str, list[str]]] = [(entrypoint, [entrypoint])]
            best_path: list[str] | None = None
            while queue:
                current, path = queue.pop(0)
                for target in local_import_targets.get(current, []):
                    if target in visited:
                        continue
                    next_path = [*path, target]
                    visited.add(target)
                    if target in risk_labels:
                        best_path = next_path
                        queue = []
                        break
                    if len(next_path) < 5:
                        queue.append((target, next_path))
            if best_path is not None:
                flows.append(" -> ".join(best_path))
            else:
                direct_targets = local_import_targets.get(entrypoint, [])
                if direct_targets:
                    flows.append(" -> ".join([entrypoint, *direct_targets[:2]]))
        return _ordered_unique(flows)[:6]

    @staticmethod
    def _build_entrypoint_review_lanes(
        *,
        entrypoint_candidates: list[str],
        local_import_targets: Mapping[str, list[str]],
        risk_markers_by_file: Mapping[str, list[str]],
    ) -> list[str]:
        lanes: list[str] = []
        for entrypoint in entrypoint_candidates[:4]:
            direct_markers = risk_markers_by_file.get(entrypoint, [])
            if direct_markers:
                lanes.append(f"{entrypoint} => {', '.join(direct_markers[:3])}")
                continue

            visited: set[str] = {entrypoint}
            queue: list[tuple[str, list[str]]] = [(entrypoint, [entrypoint])]
            best_lane: str | None = None
            while queue:
                current, path = queue.pop(0)
                for target in local_import_targets.get(current, []):
                    if target in visited:
                        continue
                    next_path = [*path, target]
                    visited.add(target)
                    markers = risk_markers_by_file.get(target, [])
                    if markers:
                        best_lane = f"{' -> '.join(next_path)} => {', '.join(markers[:3])}"
                        queue = []
                        break
                    if len(next_path) < 5:
                        queue.append((target, next_path))
            if best_lane:
                lanes.append(best_lane)
        return _ordered_unique(lanes)[:6]

    @staticmethod
    def _build_risk_family_lane_summaries(
        *,
        entrypoint_candidates: list[str],
        local_import_targets: Mapping[str, list[str]],
        risk_markers_by_file: Mapping[str, list[str]],
    ) -> list[str]:
        summaries: list[str] = []
        for entrypoint in entrypoint_candidates[:4]:
            visited: set[str] = {entrypoint}
            queue: list[tuple[str, int]] = [(entrypoint, 0)]
            marker_paths: dict[str, str] = {}

            while queue:
                current, depth = queue.pop(0)
                markers = risk_markers_by_file.get(current, [])
                for marker in markers:
                    marker_paths.setdefault(marker, current)
                if depth >= 3:
                    continue
                for target in local_import_targets.get(current, []):
                    if target in visited:
                        continue
                    visited.add(target)
                    queue.append((target, depth + 1))

            if not marker_paths:
                continue

            ordered_markers = sorted(marker_paths.items(), key=lambda item: (item[1] != entrypoint, item[0], item[1]))
            fragments: list[str] = []
            for marker, source in ordered_markers[:4]:
                if source == entrypoint:
                    fragments.append(marker)
                else:
                    fragments.append(f"{marker} via {source}")
            summaries.append(f"{entrypoint} => {', '.join(fragments)}")
        return _ordered_unique(summaries)[:6]

    @staticmethod
    def _build_entrypoint_function_family_priorities(
        *,
        entrypoint_candidates: list[str],
        local_import_targets: Mapping[str, list[str]],
        function_family_markers_by_file: Mapping[str, list[str]],
    ) -> list[str]:
        summaries: list[str] = []
        for entrypoint in entrypoint_candidates[:4]:
            visited: set[str] = {entrypoint}
            queue: list[tuple[str, int]] = [(entrypoint, 0)]
            family_paths: dict[str, str] = {}

            while queue:
                current, depth = queue.pop(0)
                families = function_family_markers_by_file.get(current, [])
                for family in families:
                    family_paths.setdefault(family, current)
                if depth >= 3:
                    continue
                for target in local_import_targets.get(current, []):
                    if target in visited:
                        continue
                    visited.add(target)
                    queue.append((target, depth + 1))

            if not family_paths:
                continue

            ordered_families = sorted(family_paths.items(), key=lambda item: (item[1] != entrypoint, item[0], item[1]))
            fragments: list[str] = []
            for family, source in ordered_families[:4]:
                if source == entrypoint:
                    fragments.append(family)
                else:
                    fragments.append(f"{family} via {source}")
            summaries.append(f"{entrypoint} => {', '.join(fragments)}")
        return _ordered_unique(summaries)[:6]

    @staticmethod
    def _risk_markers(text: str) -> list[str]:
        lowered = text.lower()
        markers: list[str] = []
        for label, token in (
            ("delegatecall", "delegatecall"),
            ("selfdestruct", "selfdestruct"),
            ("tx.origin", "tx.origin"),
            ("permit", "permit"),
            ("oracle", "latestrounddata"),
            ("reserve", "getreserves"),
            ("protocol-fee", "protocolfee"),
            ("protocol-fee", "accruedfee"),
            ("reserve-sync", "totalreserves"),
            ("reserve-sync", "reservefactor"),
            ("debt", "totaldebt"),
            ("debt", "baddebt"),
            ("collateral", "collateral"),
            ("liquidation", "liquidat"),
            ("upgrade", "upgrade"),
            ("initialize", "initialize"),
            ("reentrancy", "reentr"),
            ("transferFrom", "transferfrom"),
            ("assembly", "assembly"),
            ("vault-share", "converttoshares"),
            ("vault-assets", "converttoassets"),
        ):
            if token in lowered:
                markers.append(label)
        return list(dict.fromkeys(markers))

    @staticmethod
    def _function_family_markers(text: str) -> list[str]:
        lowered = text.lower()
        families: list[str] = []
        for label, tokens in (
            ("upgrade/admin", ("upgrade", "admin", "owner", "guardian", "operator", "grantrole", "pause", "unpause")),
            ("withdraw/claim", ("withdraw", "claim", "redeem", "unstake", "exit")),
            ("oracle/price", ("oracle", "price", "latestrounddata", "quote")),
            (
                "fee/reserve/debt",
                (
                    "protocolfee",
                    "accruedfee",
                    "totalreserves",
                    "reservefactor",
                    "reservebuffer",
                    "insurancefund",
                    "totaldebt",
                    "baddebt",
                    "writeoff",
                    "socialize",
                    "deficit",
                    "accrual",
                    "interestindex",
                    "borrowindex",
                    "skim",
                ),
            ),
            (
                "collateral/liquidation",
                (
                    "collateral",
                    "liquidat",
                    "liquidationbonus",
                    "liquidation fee",
                    "bonusbps",
                    "closefactor",
                    "healthfactor",
                    "health factor",
                    "ltv",
                    "borrow",
                    "repay",
                    "getreserves",
                ),
            ),
            ("permit/signature", ("permit", "signature", "ecrecover", "nonce")),
            ("vault/share", ("converttoshares", "converttoassets", "totalassets", "totalsupply", "previewdeposit", "shares")),
            ("rescue/sweep", ("rescue", "sweep", "recover")),
            ("token/allowance", ("transferfrom", "approve", "allowance")),
            ("proxy/storage", ("delegatecall", "implementation", "storagegap", "storage_gap", "eip1967", "uups", "sstore")),
        ):
            if any(token in lowered for token in tokens):
                families.append(label)
        return list(dict.fromkeys(families))

    @staticmethod
    def _candidate_score(relative_label: str, text: str) -> int:
        lowered_label = relative_label.lower()
        lowered_text = text.lower()
        score = 0
        for token in ("vault", "proxy", "router", "token", "pool", "market", "treasury", "bridge"):
            if token in lowered_label:
                score += 2
        for token in (
            "delegatecall",
            "selfdestruct",
            "tx.origin",
            "permit",
            "protocolfee",
            "accruedfee",
            "totalreserves",
            "reservefactor",
            "reservebuffer",
            "insurancefund",
            "totaldebt",
            "baddebt",
            "writeoff",
            "socialize",
            "deficit",
            "accrual",
            "interestindex",
            "borrowindex",
            "collateral",
            "liquidat",
            "liquidationbonus",
            "closefactor",
            "healthfactor",
            "ltv",
            "getreserves",
            "latestRoundData".lower(),
            "upgrade",
            "initialize",
            "reentr",
            "transferfrom",
            "previewdeposit",
            "converttoassets",
            "converttoshares",
        ):
            if token in lowered_text:
                score += 1
        return score
