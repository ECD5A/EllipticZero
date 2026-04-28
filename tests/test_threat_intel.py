from __future__ import annotations

import json

from app.core.threat_intel import (
    ThreatIntelCache,
    ThreatIntelProfile,
    match_threat_intel_profiles,
    render_threat_intel_cache_summary,
    render_threat_intel_sources,
    update_threat_intel_cache,
)


def test_threat_intel_update_builds_compact_profiles_without_contract_code(tmp_path) -> None:
    cache = ThreatIntelCache(tmp_path / "threat-intel")
    smartbugs_payload = json.dumps(
        [
            {
                "name": "PermitReplay.sol",
                "path": "dataset/front_running/PermitReplay.sol",
                "vulnerabilities": [{"lines": [12], "category": "front_running"}],
            },
            {
                "name": "Vault.sol",
                "path": "dataset/reentrancy/Vault.sol",
                "vulnerabilities": [{"lines": [23], "category": "reentrancy"}],
            },
        ]
    )

    summary = update_threat_intel_cache(
        cache=cache,
        source_ids=["smartbugs-curated", "slither-detectors"],
        fetch_text=lambda _url: smartbugs_payload,
    )
    profiles = cache.load_profiles()

    assert summary.profile_count >= 3
    assert any(profile.profile_id == "smartbugs-front_running" for profile in profiles)
    assert any(profile.profile_id == "slither-reentrancy-eth" for profile in profiles)
    assert "PermitReplay.sol" not in cache.profiles_path.read_text(encoding="utf-8")


def test_threat_intel_matching_uses_local_signals_before_claiming_evidence() -> None:
    profile = ThreatIntelProfile(
        profile_id="permit-replay",
        title="Permit replay profile",
        family="permit / signature replay",
        source_id="unit-test",
        source_url="https://example.invalid/profile",
        risk_hint="high",
        match_terms=["permit", "ecrecover", "nonce"],
        local_checks=["signature_replay_review_required"],
        evidence_required=["signature entrypoint", "nonce guard"],
    )

    matches = match_threat_intel_profiles(
        profiles=[profile],
        contract_code="function permitAction() external { ecrecover(hash, v, r, s); }",
        issues=["signature_replay_review_required:permitAction"],
        notes=["signature_validation_surface:permitAction"],
    )

    assert len(matches) == 1
    assert matches[0].evidence_strength == "local_signal"
    assert "signature_replay_review_required" in matches[0].matched_checks


def test_threat_intel_renderers_show_sources_and_empty_cache(tmp_path) -> None:
    cache = ThreatIntelCache(tmp_path / "empty-threat-intel")

    sources = render_threat_intel_sources(language="en")
    summary = render_threat_intel_cache_summary(cache=cache, language="en")

    assert "SmartBugs Curated metadata" in sources
    assert "Slither detector catalog" in sources
    assert "Profiles: 0" in summary
    assert "No profiles cached yet" in summary
