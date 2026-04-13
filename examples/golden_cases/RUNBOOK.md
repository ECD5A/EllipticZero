# Golden Cases Runbook

Use this runbook when you want to evaluate EllipticZero quickly without private
client code or live provider keys.

## 1. Check Local Readiness

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m app.main --list-golden-cases
```

Expected evaluator signal:

- the CLI starts
- benchmark packs are listed
- golden cases are listed
- missing optional tools are reported as optional or unavailable, not hidden

Shortest direct run:

```powershell
python -m app.main --golden-case ecc-secp256k1-point-format-edge
python -m app.main --golden-case contract-repo-scale-lending-protocol
```

## 2. Run ECC Domain Completeness

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether secp256k1 curve-domain assumptions are complete enough for cautious defensive reporting."
```

Look for:

- selected pack and executed pack steps
- curve-domain metadata
- bounded confidence and manual-review boundaries

## 3. Run ECC Point-Format Edge

```powershell
python -m app.main --pack point_format_inspection_pack "Inspect a compressed secp256k1 public-key encoding edge and keep format evidence separate from stronger cryptographic claims."
```

Look for:

- format or prefix evidence
- bounded consistency output
- no private-key recovery or exploit claim

## 4. Run Single-Contract Smart-Contract Cases

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticVault.sol --pack vault_permission_benchmark_pack "Benchmark vault share-accounting, permission, and externally reachable value-flow review lanes."
```

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticGovernanceTimelock.sol --pack governance_timelock_benchmark_pack "Benchmark governance timelock, upgrade-control, and emergency-lane review surfaces."
```

Look for:

- parser and surface output
- manual review queue
- bounded confidence
- no claim of a confirmed exploit from pattern evidence alone

## 5. Run Repo-Scale Smart-Contract Case

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\protocols\SyntheticLendingProtocol\contracts\LendingPool.sol --pack lending_protocol_benchmark_pack "Benchmark the scoped lending protocol for collateral, liquidation, reserve, fee, and debt-accounting review lanes."
```

Look for:

- bounded contract inventory
- local import graph
- entrypoint review lanes
- collateral/liquidation and fee/reserve/debt-accounting lanes
- manual review boundaries

## 6. Read Expected Report Shapes

Compare output against:

- [EXPECTED_REPORT_SHAPES.md](EXPECTED_REPORT_SHAPES.md)
- [golden_manifest.json](golden_manifest.json)

The report does not need identical wording. It should preserve the same
evidence posture: what was observed locally, what is only a review priority,
and what still requires expert validation.
