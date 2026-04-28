from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

FetchText = Callable[[str], str]

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ThreatIntelSource:
    source_id: str
    title: str
    source_url: str
    adapter: str
    description: str
    update_enabled: bool = True


@dataclass(frozen=True)
class ThreatIntelProfile:
    profile_id: str
    title: str
    family: str
    source_id: str
    source_url: str
    risk_hint: str
    match_terms: list[str] = field(default_factory=list)
    local_checks: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    allowed_behavior: str = "defensive review only; do not execute remote code"
    case_count: int = 0
    updated_at: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ThreatIntelProfile":
        return cls(
            profile_id=str(payload.get("profile_id", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            family=str(payload.get("family", "")).strip(),
            source_id=str(payload.get("source_id", "")).strip(),
            source_url=str(payload.get("source_url", "")).strip(),
            risk_hint=str(payload.get("risk_hint", "medium")).strip().lower() or "medium",
            match_terms=_string_list(payload.get("match_terms")),
            local_checks=_string_list(payload.get("local_checks")),
            evidence_required=_string_list(payload.get("evidence_required")),
            allowed_behavior=str(payload.get("allowed_behavior", "")).strip()
            or "defensive review only; do not execute remote code",
            case_count=int(payload.get("case_count", 0) or 0),
            updated_at=_optional_str(payload.get("updated_at")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ThreatIntelMatch:
    profile_id: str
    title: str
    family: str
    source_id: str
    source_url: str
    risk_hint: str
    matched_terms: list[str]
    matched_checks: list[str]
    score: int
    evidence_strength: str
    evidence_required: list[str]
    allowed_behavior: str

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ThreatIntelUpdateSummary:
    cache_dir: str
    updated_at: str
    profile_count: int
    source_results: list[str]
    errors: list[str] = field(default_factory=list)


ALLOWED_THREAT_INTEL_SOURCES: tuple[ThreatIntelSource, ...] = (
    ThreatIntelSource(
        source_id="smartbugs-curated",
        title="SmartBugs Curated metadata",
        source_url="https://raw.githubusercontent.com/smartbugs/smartbugs-curated/main/vulnerabilities.json",
        adapter="smartbugs_vulnerabilities_json",
        description="Annotated Solidity vulnerability metadata used to derive compact review profiles.",
    ),
    ThreatIntelSource(
        source_id="slither-detectors",
        title="Slither detector catalog",
        source_url="https://github.com/crytic/slither",
        adapter="slither_detector_mapping",
        description="Detector-family mapping aligned with Slither's public smart-contract analysis catalog.",
    ),
    ThreatIntelSource(
        source_id="evmbench-reference",
        title="EVMbench reference",
        source_url="https://openai.com/index/introducing-evmbench/",
        adapter="reference_only",
        description="Reference source for benchmark design; not downloaded into the local cache by default.",
        update_enabled=False,
    ),
    ThreatIntelSource(
        source_id="defihacklabs-reference",
        title="DeFiHackLabs reference",
        source_url="https://github.com/SunWeb3Sec/DeFiHackLabs",
        adapter="reference_only",
        description="Reference source for historical incident reproduction; exploit code is not fetched or run.",
        update_enabled=False,
    ),
)


SMARTBUGS_CATEGORY_PROFILES: dict[str, dict[str, Any]] = {
    "access_control": {
        "family": "access control",
        "risk_hint": "high",
        "match_terms": ["owner", "admin", "role", "onlyowner", "tx.origin", "upgrade", "pause"],
        "local_checks": [
            "unguarded_admin_surface",
            "unguarded_role_management_surface",
            "unguarded_pause_control_surface",
            "unguarded_upgrade_surface",
            "tx_origin_auth_surface",
            "public_initializer_surface",
        ],
        "evidence_required": ["entrypoint", "missing guard signal", "role or owner path", "manual review note"],
    },
    "reentrancy": {
        "family": "reentrancy / external call ordering",
        "risk_hint": "high",
        "match_terms": ["withdraw", "call{value", ".call.value", "balances", "reentrancy"],
        "local_checks": [
            "reentrancy_review_required",
            "state_transition_after_external_call",
            "accounting_update_after_external_call",
        ],
        "evidence_required": ["external call site", "state update order", "balance/accounting path"],
    },
    "arithmetic": {
        "family": "arithmetic / unchecked math",
        "risk_hint": "medium",
        "match_terms": ["unchecked", "overflow", "underflow", "+=", "-=", "*="],
        "local_checks": ["unchecked_blocks_present"],
        "evidence_required": ["math operation", "compiler version", "bounds or invariant"],
    },
    "unchecked_low_level_calls": {
        "family": "unchecked low-level calls",
        "risk_hint": "high",
        "match_terms": [".call(", ".send(", ".delegatecall(", "low-level"],
        "local_checks": [
            "unchecked_external_call_surface",
            "unchecked_token_transfer_surface",
            "unchecked_token_transfer_from_surface",
        ],
        "evidence_required": ["call site", "return handling", "failure behavior"],
    },
    "denial_of_service": {
        "family": "denial of service / unbounded iteration",
        "risk_hint": "medium",
        "match_terms": ["for (", "while (", "loop", "array", "external call in loop"],
        "local_checks": ["loop_review", "external_call_in_loop"],
        "evidence_required": ["loop bound", "caller-controlled collection", "external dependency"],
    },
    "bad_randomness": {
        "family": "entropy / randomness",
        "risk_hint": "high",
        "match_terms": ["block.timestamp", "blockhash", "prevrandao", "random", "keccak256"],
        "local_checks": ["entropy_source_review_required", "time_dependency_review"],
        "evidence_required": ["entropy source", "value at risk", "miner or sequencer influence"],
    },
    "front_running": {
        "family": "front-running / allowance race",
        "risk_hint": "medium",
        "match_terms": ["approve", "allowance", "permit", "deadline"],
        "local_checks": ["approve_race_review_required", "signature_replay_review_required"],
        "evidence_required": ["transaction ordering dependency", "allowance or signature state", "recheck path"],
    },
    "time_manipulation": {
        "family": "time dependency",
        "risk_hint": "medium",
        "match_terms": ["block.timestamp", "now", "deadline", "updatedat"],
        "local_checks": ["time_dependency_review", "oracle_staleness_review_required"],
        "evidence_required": ["timestamp dependency", "allowed drift", "state transition impact"],
    },
    "short_addresses": {
        "family": "ABI / input encoding",
        "risk_hint": "low",
        "match_terms": ["abi.encodepacked", "calldata", "bytes"],
        "local_checks": ["signature_replay_review_required"],
        "evidence_required": ["input boundary", "ABI encoding assumption", "parser or caller constraints"],
    },
}


SLITHER_REFERENCE_PROFILES: tuple[ThreatIntelProfile, ...] = (
    ThreatIntelProfile(
        profile_id="slither-reentrancy-eth",
        title="Slither reentrancy detector family",
        family="reentrancy / external call ordering",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["reentrancy", "withdraw", "call{value", ".call.value"],
        local_checks=[
            "reentrancy_review_required",
            "state_transition_after_external_call",
            "accounting_update_after_external_call",
        ],
        evidence_required=["external call", "state update ordering", "reentrancy guard posture"],
    ),
    ThreatIntelProfile(
        profile_id="slither-unchecked-transfer",
        title="Slither unchecked transfer detector family",
        family="unchecked token or low-level call result",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["transfer(", "transferfrom(", ".call(", ".send("],
        local_checks=[
            "unchecked_token_transfer_surface",
            "unchecked_token_transfer_from_surface",
            "unchecked_external_call_surface",
        ],
        evidence_required=["call result handling", "token or low-level call site", "failure behavior"],
    ),
    ThreatIntelProfile(
        profile_id="slither-unprotected-upgrade",
        title="Slither unprotected upgrade detector family",
        family="upgrade / proxy control",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["upgrade", "implementation", "delegatecall", "proxy"],
        local_checks=[
            "unguarded_upgrade_surface",
            "unvalidated_implementation_target",
            "proxy_fallback_delegatecall_review_required",
            "storage_slot_write_review_required",
        ],
        evidence_required=["upgrade entrypoint", "access guard", "implementation validation"],
    ),
    ThreatIntelProfile(
        profile_id="slither-controlled-delegatecall",
        title="Slither controlled delegatecall detector family",
        family="delegatecall target control",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["delegatecall", "target", "implementation"],
        local_checks=["user_supplied_delegatecall_target", "unguarded_delegatecall_surface"],
        evidence_required=["delegatecall target", "caller control path", "access guard"],
    ),
    ThreatIntelProfile(
        profile_id="slither-tx-origin",
        title="Slither tx.origin detector family",
        family="tx.origin authorization",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="medium",
        match_terms=["tx.origin"],
        local_checks=["tx_origin_usage", "tx_origin_auth_surface"],
        evidence_required=["authorization expression", "caller assumption", "manual review note"],
    ),
    ThreatIntelProfile(
        profile_id="slither-weak-prng",
        title="Slither weak randomness detector family",
        family="entropy / randomness",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["block.timestamp", "blockhash", "prevrandao", "random"],
        local_checks=["entropy_source_review_required", "time_dependency_review"],
        evidence_required=["entropy source", "economic impact", "sequencer or miner influence"],
    ),
    ThreatIntelProfile(
        profile_id="slither-arbitrary-send-erc20-permit",
        title="Slither arbitrary transfer/permit detector family",
        family="permit / arbitrary token movement",
        source_id="slither-detectors",
        source_url="https://github.com/crytic/slither",
        risk_hint="high",
        match_terms=["permit", "transferfrom", "allowance", "ecrecover"],
        local_checks=[
            "arbitrary_from_transfer_surface",
            "signature_replay_review_required",
            "approve_race_review_required",
        ],
        evidence_required=["from/spender authority", "nonce or deadline binding", "token movement path"],
    ),
)


class ThreatIntelCache:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else default_threat_intel_cache_dir()
        self.profiles_path = self.cache_dir / "profiles.json"

    def load_profiles(self) -> list[ThreatIntelProfile]:
        if not self.profiles_path.exists():
            return []
        try:
            payload = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if int(payload.get("schema_version", 0) or 0) != SCHEMA_VERSION:
            return []
        profiles = payload.get("profiles", [])
        if not isinstance(profiles, list):
            return []
        return [
            profile
            for item in profiles
            if isinstance(item, dict)
            for profile in [_safe_profile_from_mapping(item)]
            if profile is not None
        ]

    def save_profiles(self, profiles: list[ThreatIntelProfile], *, updated_at: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": updated_at,
            "profile_count": len(profiles),
            "profiles": [profile.to_mapping() for profile in profiles],
        }
        self.profiles_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def status(self) -> dict[str, Any]:
        profiles = self.load_profiles()
        updated_at = None
        if self.profiles_path.exists():
            try:
                payload = json.loads(self.profiles_path.read_text(encoding="utf-8"))
                updated_at = payload.get("updated_at")
            except (OSError, json.JSONDecodeError):
                updated_at = None
        return {
            "cache_dir": str(self.cache_dir),
            "profiles_path": str(self.profiles_path),
            "profile_count": len(profiles),
            "updated_at": updated_at,
            "source_counts": dict(Counter(profile.source_id for profile in profiles)),
        }


def default_threat_intel_cache_dir() -> Path:
    if override := os.getenv("ELLIPTICZERO_THREAT_INTEL_DIR"):
        return Path(override).expanduser()
    if local_app_data := os.getenv("LOCALAPPDATA"):
        return Path(local_app_data) / "EllipticZero" / "threat-intel"
    return Path.home() / ".ellipticzero" / "threat-intel"


def update_threat_intel_cache(
    *,
    cache: ThreatIntelCache | None = None,
    source_ids: list[str] | None = None,
    fetch_text: FetchText | None = None,
) -> ThreatIntelUpdateSummary:
    cache = cache or ThreatIntelCache()
    selected_ids = set(source_ids or [source.source_id for source in ALLOWED_THREAT_INTEL_SOURCES if source.update_enabled])
    updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    profiles: list[ThreatIntelProfile] = []
    source_results: list[str] = []
    errors: list[str] = []
    fetch = fetch_text or _fetch_text
    sources_by_id = {source.source_id: source for source in ALLOWED_THREAT_INTEL_SOURCES}

    for source_id in sorted(selected_ids):
        source = sources_by_id.get(source_id)
        if source is None:
            errors.append(f"{source_id}: source is not allowlisted")
            continue
        if not source.update_enabled:
            source_results.append(f"{source_id}: reference-only source skipped")
            continue
        try:
            if source.adapter == "smartbugs_vulnerabilities_json":
                raw = fetch(source.source_url)
                source_profiles = _profiles_from_smartbugs(raw, updated_at=updated_at)
            elif source.adapter == "slither_detector_mapping":
                source_profiles = [profile_with_updated_at(profile, updated_at) for profile in SLITHER_REFERENCE_PROFILES]
            else:
                source_profiles = []
        except Exception as exc:  # pragma: no cover - defensive boundary around remote metadata.
            errors.append(f"{source_id}: {exc}")
            continue
        profiles.extend(source_profiles)
        source_results.append(f"{source_id}: {len(source_profiles)} profile(s)")

    profiles = _dedupe_profiles(profiles)
    if profiles:
        cache.save_profiles(profiles, updated_at=updated_at)
    return ThreatIntelUpdateSummary(
        cache_dir=str(cache.cache_dir),
        updated_at=updated_at,
        profile_count=len(profiles),
        source_results=source_results,
        errors=errors,
    )


def match_threat_intel_profiles(
    *,
    profiles: list[ThreatIntelProfile],
    contract_code: str,
    issues: list[str],
    notes: list[str],
    max_matches: int = 8,
) -> list[ThreatIntelMatch]:
    if not profiles:
        return []
    text = "\n".join([contract_code, *issues, *notes]).lower()
    signal_families = {_signal_family(item) for item in [*issues, *notes]}
    matches: list[ThreatIntelMatch] = []
    for profile in profiles:
        matched_terms = [
            term
            for term in profile.match_terms
            if term and len(term) > 2 and term.lower() in text
        ]
        matched_checks = [
            check
            for check in profile.local_checks
            if check in signal_families or any(item.startswith(f"{check}:") for item in [*issues, *notes])
        ]
        if not matched_terms and not matched_checks:
            continue
        score = len(matched_terms) + len(matched_checks) * 3
        matches.append(
            ThreatIntelMatch(
                profile_id=profile.profile_id,
                title=profile.title,
                family=profile.family,
                source_id=profile.source_id,
                source_url=profile.source_url,
                risk_hint=profile.risk_hint,
                matched_terms=matched_terms[:6],
                matched_checks=matched_checks[:6],
                score=score,
                evidence_strength="local_signal" if matched_checks else "context",
                evidence_required=profile.evidence_required[:6],
                allowed_behavior=profile.allowed_behavior,
            )
        )
    return sorted(
        matches,
        key=lambda match: (_risk_rank(match.risk_hint), match.score, len(match.matched_checks)),
        reverse=True,
    )[:max_matches]


def render_threat_intel_sources(*, language: str = "en") -> str:
    ru = language.lower().startswith("ru")
    title = "Источники профилей известных кейсов" if ru else "Threat-intel sources"
    lines = [title, ""]
    for source in ALLOWED_THREAT_INTEL_SOURCES:
        mode = "обновляется" if source.update_enabled else "только справочно"
        if not ru:
            mode = "updatable" if source.update_enabled else "reference only"
        lines.append(f"- {source.title}: {source.source_url}")
        lines.append(f"  adapter={source.adapter}; mode={mode}")
    return "\n".join(lines)


def render_threat_intel_cache_summary(
    *,
    cache: ThreatIntelCache | None = None,
    language: str = "en",
) -> str:
    cache = cache or ThreatIntelCache()
    status = cache.status()
    ru = language.lower().startswith("ru")
    lines = [
        "Сводка кэша профилей известных кейсов" if ru else "Threat-intel cache summary",
        "",
        f"{'Каталог кэша' if ru else 'Cache directory'}: {status['cache_dir']}",
        f"{'Профилей' if ru else 'Profiles'}: {status['profile_count']}",
        f"{'Обновлено' if ru else 'Updated'}: {status.get('updated_at') or ('нет' if ru else 'none')}",
    ]
    source_counts = status.get("source_counts")
    if isinstance(source_counts, dict) and source_counts:
        lines.append("")
        lines.append("Источники:" if ru else "Sources:")
        for source_id, count in sorted(source_counts.items()):
            lines.append(f"- {source_id}: {count}")
    else:
        lines.append("")
        lines.append(
            "Профили пока не загружены. Используй пункт ОБНОВИТЬ ПРОФИЛИ в меню."
            if ru
            else "No profiles cached yet. Use Update profiles from the menu."
        )
    return "\n".join(lines)


def render_threat_intel_update_summary(
    summary: ThreatIntelUpdateSummary,
    *,
    language: str = "en",
) -> str:
    ru = language.lower().startswith("ru")
    lines = [
        "Обновление профилей известных кейсов" if ru else "Threat-intel update",
        "",
        f"{'Каталог кэша' if ru else 'Cache directory'}: {summary.cache_dir}",
        f"{'Профилей' if ru else 'Profiles'}: {summary.profile_count}",
        f"{'Обновлено' if ru else 'Updated'}: {summary.updated_at}",
    ]
    if summary.source_results:
        lines.append("")
        lines.append("Источники:" if ru else "Sources:")
        lines.extend(f"- {item}" for item in summary.source_results)
    if summary.errors:
        lines.append("")
        lines.append("Ошибки:" if ru else "Errors:")
        lines.extend(f"- {item}" for item in summary.errors)
    return "\n".join(lines)


def profile_with_updated_at(profile: ThreatIntelProfile, updated_at: str) -> ThreatIntelProfile:
    payload = profile.to_mapping()
    payload["updated_at"] = updated_at
    return ThreatIntelProfile.from_mapping(payload)


def _profiles_from_smartbugs(raw_json: str, *, updated_at: str) -> list[ThreatIntelProfile]:
    payload = json.loads(raw_json)
    if not isinstance(payload, list):
        raise ValueError("SmartBugs vulnerabilities.json must be a list.")
    category_counts: Counter[str] = Counter()
    for item in payload:
        if not isinstance(item, dict):
            continue
        vulnerabilities = item.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            continue
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            category = _normalize_category(str(vulnerability.get("category", "")))
            if category:
                category_counts[category] += 1

    profiles: list[ThreatIntelProfile] = []
    for category, count in sorted(category_counts.items()):
        spec = SMARTBUGS_CATEGORY_PROFILES.get(category) or _generic_category_profile(category)
        profiles.append(
            ThreatIntelProfile(
                profile_id=f"smartbugs-{category}",
                title=f"SmartBugs {category.replace('_', ' ')} profile",
                family=str(spec["family"]),
                source_id="smartbugs-curated",
                source_url="https://github.com/smartbugs/smartbugs-curated",
                risk_hint=str(spec["risk_hint"]),
                match_terms=list(spec["match_terms"]),
                local_checks=list(spec["local_checks"]),
                evidence_required=list(spec["evidence_required"]),
                case_count=count,
                updated_at=updated_at,
            )
        )
    return profiles


def _generic_category_profile(category: str) -> dict[str, Any]:
    words = [part for part in category.split("_") if part]
    return {
        "family": category.replace("_", " "),
        "risk_hint": "medium",
        "match_terms": words,
        "local_checks": [],
        "evidence_required": ["matched surface", "local detector signal", "manual review note"],
    }


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "EllipticZero threat-intel metadata updater"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(1_500_000)
    return body.decode("utf-8")


def _dedupe_profiles(profiles: list[ThreatIntelProfile]) -> list[ThreatIntelProfile]:
    deduped: dict[str, ThreatIntelProfile] = {}
    for profile in profiles:
        if profile.profile_id:
            deduped[profile.profile_id] = profile
    return [deduped[key] for key in sorted(deduped)]


def _safe_profile_from_mapping(payload: dict[str, Any]) -> ThreatIntelProfile | None:
    profile = ThreatIntelProfile.from_mapping(payload)
    if not profile.profile_id or not profile.family or not profile.source_id:
        return None
    return profile


def _normalize_category(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _signal_family(value: str) -> str:
    return value.split(":", 1)[0].strip().lower()


def _risk_rank(value: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(value.strip().lower(), 0)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
