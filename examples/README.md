# EllipticZero Examples

These examples are meant to be safe, bounded, and replayable. They use local
mock mode unless you explicitly configure a hosted provider.

Do not paste API keys into issues, commits, screenshots, or chat transcripts.
Set keys only in your local shell or local `.env`.

For shortened sample report shapes, see [SAMPLE_OUTPUTS.md](SAMPLE_OUTPUTS.md).
For reproducible synthetic evaluator cases, see
[golden_cases/README.md](golden_cases/README.md).

Fast evaluator path:

```powershell
python -m app.main --list-golden-cases
python -m app.main --golden-case contract-repo-scale-lending-protocol
python -m app.main --golden-case ecc-secp256k1-point-format-edge
```

## Readiness Checks

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m app.main --show-routing
```

## Smart-Contract Audit

Run a bounded review from inline Solidity:

```powershell
python -m app.main --domain smart_contract_audit --contract-code "pragma solidity ^0.8.20; contract Vault { mapping(address => uint256) public balances; }" "Review reachable state, value-flow, and externally visible surfaces."
```

Run a bounded review from a local contract file:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for low-level call review surfaces and externally reachable value flow."
```

Run a static benchmark pack against a local contract file:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

Run a repo-casebook benchmark when the contract belongs to a local protocol
tree:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
```

## ECC Research

Run a direct bounded ECC session:

```powershell
python -m app.main "Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output."
```

Run the ECC family-depth benchmark pack:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions for defensive ECC analysis."
```

Run subgroup and cofactor hygiene checks:

```powershell
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, and twist-hygiene assumptions under bounded local checks."
```

Run domain-completeness checks:

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether curve-domain assumptions are complete enough for a cautious defensive report."
```

## Before/After Validation

Attach a saved baseline session to a fresh bounded run:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the bounded audit and record before/after deltas against the saved baseline session."
```

Replay an existing saved session:

```powershell
python -m app.main --replay-session .\artifacts\sessions\session_id.json
```

## Hosted Provider Smoke Test

Skip this section unless you have a local API key configured.

OpenAI:

```powershell
$env:OPENAI_API_KEY="local-key-here"
python -m app.main --live-provider-smoke openai --live-smoke-model gpt-4.1-mini
```

OpenRouter:

```powershell
$env:OPENROUTER_API_KEY="local-key-here"
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

## Artifacts

Completed runs can write sessions, traces, comparison output, manifests, and
bundles under `artifacts/`. Keep these artifacts when you need a reproducible
evidence trail, and remove sensitive local inputs before sharing reports.
