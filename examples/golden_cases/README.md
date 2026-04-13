# Golden Synthetic Cases

This directory contains safe synthetic cases for evaluating EllipticZero without
needing a private client repository or live API keys.

The goal is not to prove that every issue is detected. The goal is to make the
expected workflow legible:

- choose a bounded case
- run a matching benchmark pack
- inspect executed pack steps and local evidence
- check whether the final report preserves confidence limits and manual-review lanes

## Contents

- [golden_manifest.json](golden_manifest.json) records the supported cases, their expected packs, and the report-shape expectations.
- [RUNBOOK.md](RUNBOOK.md) gives a quick evaluator path through the golden cases.
- [EXPECTED_REPORT_SHAPES.md](EXPECTED_REPORT_SHAPES.md) explains what a useful report should contain for each case.
- [contracts/SyntheticVault.sol](contracts/SyntheticVault.sol) is a safe vault/permission review fixture.
- [contracts/SyntheticGovernanceTimelock.sol](contracts/SyntheticGovernanceTimelock.sol) is a safe governance/timelock and upgrade-control fixture.
- [protocols/SyntheticLendingProtocol](protocols/SyntheticLendingProtocol) is a safe repo-scale lending protocol fixture.
- [ecc/secp256k1_metadata_seed.txt](ecc/secp256k1_metadata_seed.txt) is an ECC domain-completeness seed.
- [ecc/curve25519_subgroup_seed.txt](ecc/curve25519_subgroup_seed.txt) is an ECC subgroup/cofactor hygiene seed.
- [ecc/secp256k1_point_format_edge_seed.txt](ecc/secp256k1_point_format_edge_seed.txt) is an ECC point-format edge seed.

## Quick Runs

ECC domain completeness:

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether secp256k1 curve-domain assumptions are complete enough for cautious defensive reporting."
```

ECC subgroup hygiene:

```powershell
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, twist, and encoding assumptions for 25519-family defensive analysis."
```

ECC point-format edge:

```powershell
python -m app.main --pack point_format_inspection_pack "Inspect a compressed secp256k1 public-key encoding edge and keep format evidence separate from stronger cryptographic claims."
```

Vault/permission smart-contract lane:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticVault.sol --pack vault_permission_benchmark_pack "Benchmark vault share-accounting, permission, and externally reachable value-flow review lanes."
```

Governance/timelock smart-contract lane:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticGovernanceTimelock.sol --pack governance_timelock_benchmark_pack "Benchmark governance timelock, upgrade-control, and emergency-lane review surfaces."
```

Repo-scale lending protocol lane:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\protocols\SyntheticLendingProtocol\contracts\LendingPool.sol --pack lending_protocol_benchmark_pack "Benchmark the scoped lending protocol for collateral, liquidation, reserve, fee, and debt-accounting review lanes."
```

## Evaluation Notes

These cases are intentionally synthetic. They are designed to exercise parser,
surface, benchmark, report, and confidence-calibration paths, not to publish
real exploit material.

Good output should preserve what was actually observed locally. It should not
upgrade a review lane into a confirmed vulnerability unless additional local
evidence supports that claim.
