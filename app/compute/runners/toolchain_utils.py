from __future__ import annotations

import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from packaging.version import InvalidVersion, Version


def resolve_local_binary(binary_name: str) -> str | None:
    if not binary_name:
        return None
    explicit_path = resolve_explicit_binary_path(binary_name)
    if explicit_path is not None:
        return explicit_path
    if shutil.which(binary_name):
        return binary_name
    candidate = python_environment_binary(binary_name)
    if candidate is not None:
        return str(candidate)
    return None


def python_environment_binary(binary_name: str) -> Path | None:
    if not binary_name:
        return None
    if resolve_explicit_binary_path(binary_name) is not None:
        return None
    scripts_dir = Path(sys.executable).resolve().parent
    names = [binary_name]
    if not binary_name.lower().endswith(".exe"):
        names.append(f"{binary_name}.exe")
    for candidate_name in names:
        candidate = scripts_dir / candidate_name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def list_managed_solc_versions(managed_dir: str | None) -> list[str]:
    install_path = _normalize_directory(managed_dir)
    if install_path is None:
        return []
    try:
        from solcx import get_installed_solc_versions

        versions = get_installed_solc_versions(solcx_binary_path=install_path)
    except Exception:
        return []
    return [str(version) for version in sorted(versions)]


def resolve_managed_solc_binary(
    *,
    managed_dir: str | None,
    preferred_version: str | None,
    pragma_spec: str | None = None,
    require_pragma_match: bool = False,
) -> tuple[str | None, str | None]:
    install_path = _normalize_directory(managed_dir)
    if install_path is None:
        return None, None

    try:
        from solcx import get_installed_solc_versions
        from solcx.install import get_executable
    except Exception:
        return None, None

    try:
        installed = sorted(get_installed_solc_versions(solcx_binary_path=install_path))
    except Exception:
        return None, None
    if not installed:
        return None, None

    selected = _select_solc_version(
        installed_versions=[str(version) for version in installed],
        preferred_version=preferred_version,
        pragma_spec=pragma_spec,
        require_pragma_match=require_pragma_match,
    )
    if selected is None:
        return None, None

    try:
        executable = get_executable(selected, solcx_binary_path=install_path)
    except Exception:
        return None, None
    if not executable.exists() or not executable.is_file():
        return None, None
    return str(executable), str(selected)


def extract_solidity_pragma_spec(contract_code: str) -> str | None:
    match = re.search(r"\bpragma\s+solidity\s+([^;]+);", contract_code)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def extract_semver(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"\b\d+\.\d+\.\d+\b", text)
    if match is None:
        return None
    return match.group(0)


def select_best_solc_version(
    *,
    installed_versions: list[str],
    preferred_version: str | None,
    pragma_spec: str | None,
    require_pragma_match: bool = False,
) -> str | None:
    return _select_solc_version(
        installed_versions=installed_versions,
        preferred_version=preferred_version,
        pragma_spec=pragma_spec,
        require_pragma_match=require_pragma_match,
    )


def resolve_explicit_binary_path(binary_name: str) -> str | None:
    path = Path(binary_name).expanduser()
    looks_like_path = path.is_absolute() or path.parent != Path(".")
    if not looks_like_path:
        return None
    if path.exists() and path.is_file():
        return str(path)
    return None


def _normalize_directory(managed_dir: str | None) -> Path | None:
    if not managed_dir:
        return None
    candidate = Path(managed_dir).expanduser()
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _select_solc_version(
    *,
    installed_versions: list[str],
    preferred_version: str | None,
    pragma_spec: str | None,
    require_pragma_match: bool,
) -> str | None:
    normalized_versions = _sorted_version_strings(installed_versions)
    if not normalized_versions:
        return None

    matching_versions = _matching_solc_versions(normalized_versions, pragma_spec)
    if matching_versions:
        if preferred_version and preferred_version.strip() in matching_versions:
            return preferred_version.strip()
        return matching_versions[-1]

    if require_pragma_match and pragma_spec and pragma_spec.strip():
        return None

    if preferred_version and preferred_version.strip() in normalized_versions:
        return preferred_version.strip()
    return normalized_versions[-1]


def _sorted_version_strings(installed_versions: list[str]) -> list[str]:
    parsed: list[tuple[Version, str]] = []
    for value in installed_versions:
        stripped = str(value).strip()
        if not stripped:
            continue
        try:
            parsed.append((Version(stripped), stripped))
        except InvalidVersion:
            continue
    parsed.sort(key=lambda item: item[0])
    return [item[1] for item in parsed]


def _matching_solc_versions(installed_versions: list[str], pragma_spec: str | None) -> list[str]:
    if not pragma_spec or not pragma_spec.strip():
        return []
    predicates = _pragma_predicates(pragma_spec)
    if not predicates:
        return []
    matches: list[str] = []
    for value in installed_versions:
        try:
            version = Version(value)
        except InvalidVersion:
            continue
        if all(predicate(version) for predicate in predicates):
            matches.append(value)
    return matches


def _pragma_predicates(pragma_spec: str) -> list[Callable[[Version], bool]]:
    normalized = pragma_spec.strip()
    if not normalized:
        return []
    normalized = normalized.replace("pragma solidity", "").replace(";", "").strip()
    if not normalized:
        return []
    if "||" in normalized:
        normalized = normalized.split("||", 1)[0].strip()

    predicates: list[Callable[[Version], bool]] = []
    for token in re.split(r"[,\s]+", normalized):
        stripped = token.strip()
        if not stripped:
            continue
        predicate = _token_predicate(stripped)
        if predicate is not None:
            predicates.append(predicate)
    return predicates


def _token_predicate(token: str):
    if token.startswith("^"):
        version = _parse_version(token[1:])
        if version is None:
            return None
        upper_bound = _caret_upper_bound(version)
        return lambda candidate, lower=version, upper=upper_bound: lower <= candidate < upper
    if token.startswith("~"):
        version = _parse_version(token[1:])
        if version is None:
            return None
        upper_bound = _tilde_upper_bound(version)
        return lambda candidate, lower=version, upper=upper_bound: lower <= candidate < upper

    for operator in (">=", "<=", ">", "<", "==", "="):
        if token.startswith(operator):
            version = _parse_version(token[len(operator) :])
            if version is None:
                return None
            if operator == ">=":
                return lambda candidate, lower=version: candidate >= lower
            if operator == "<=":
                return lambda candidate, upper=version: candidate <= upper
            if operator == ">":
                return lambda candidate, lower=version: candidate > lower
            if operator == "<":
                return lambda candidate, upper=version: candidate < upper
            return lambda candidate, exact=version: candidate == exact

    version = _parse_version(token)
    if version is None:
        return None
    return lambda candidate, exact=version: candidate == exact


def _parse_version(value: str) -> Version | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Version(stripped)
    except InvalidVersion:
        return None


def _caret_upper_bound(version: Version) -> Version:
    release = list(version.release) + [0, 0, 0]
    major, minor, patch = release[:3]
    if major > 0:
        return Version(f"{major + 1}.0.0")
    if minor > 0:
        return Version(f"0.{minor + 1}.0")
    return Version(f"0.0.{patch + 1}")


def _tilde_upper_bound(version: Version) -> Version:
    release = list(version.release) + [0, 0, 0]
    major, minor, _patch = release[:3]
    return Version(f"{major}.{minor + 1}.0")
