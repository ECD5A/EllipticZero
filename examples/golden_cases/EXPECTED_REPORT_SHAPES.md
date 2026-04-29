# Expected Report Shapes

These shapes describe what a useful EllipticZero report should preserve when
running the golden synthetic cases. They are intentionally qualitative because
local tools, optional adapters, and provider configuration can change the exact
wording and artifact counts.

## `ecc-secp256k1-domain-completeness`

Expected useful output:

- selected pack is `ecc_domain_completeness_benchmark_pack`
- executed pack steps are visible in the session and report
- curve-domain metadata is described as local evidence
- generator/order/cofactor or family-completeness boundaries are clear
- confidence remains bounded and does not claim a cryptographic break

Evaluator pass signal:

- the report makes it easy to see what was checked and what remains a manual-review question

## `ecc-25519-subgroup-hygiene`

Expected useful output:

- selected pack is `ecc_subgroup_hygiene_benchmark_pack`
- subgroup, cofactor, twist, or encoding lanes are visible
- any coordinate or family caveat stays separated from a production finding
- confidence remains bounded
- manual-review boundaries are preserved

Evaluator pass signal:

- the report distinguishes local review signals from verified implementation evidence

## `ecc-secp256k1-point-format-edge`

Expected useful output:

- selected pack is `point_format_inspection_pack`
- point-format or prefix evidence is visible
- bounded consistency output is separated from stronger cryptographic claims
- confidence remains bounded
- report avoids claiming private-key recovery or a production library vulnerability

Evaluator pass signal:

- the report treats malformed or edge-format evidence as a review signal, not as an exploit

## `contract-vault-permission-lane`

Expected useful output:

- selected pack is `vault_permission_benchmark_pack`
- parser output includes the synthetic vault contract and its externally reachable functions
- surface summary highlights payable, value-flow, share/accounting, permission, or signature-style lanes when present
- finding cards appear near the top and preserve potential finding, evidence, why it matters, fix direction, and recheck path
- evidence coverage and reproducibility outputs are visible without digging into raw JSON artifacts
- toolchain fingerprint and secret-redaction posture remain available in the export-quality section
- manual review queue and residual-risk lines remain visible
- report avoids claiming a confirmed exploit from pattern evidence alone

Evaluator pass signal:

- the report gives a buyer or reviewer a clear first triage path without overstating the result

## `contract-reentrancy-review-lane`

Expected useful output:

- selected pack is `contract_static_benchmark_pack`
- parser output includes the synthetic reentrancy-style vault and its externally reachable functions
- surface or pattern summary highlights external-call ordering, value-flow, withdrawal accounting, or reentrancy-adjacent lanes when present
- manual review queue and bounded confidence remain visible
- report avoids claiming a confirmed exploit from pattern evidence alone

Evaluator pass signal:

- the report shows a concrete review lane and recheck path without turning the synthetic fixture into operational exploit guidance

## `contract-governance-timelock-lane`

Expected useful output:

- selected pack is `governance_timelock_benchmark_pack`
- governance, timelock, emergency, upgrade-control, delegatecall, or timestamp lanes are visible when local parsing supports them
- execution and upgrade surfaces are framed as bounded review priorities
- manual review queue and exit criteria remain visible
- report avoids claiming complete upgrade safety or a confirmed takeover path

Evaluator pass signal:

- the report shows where a human reviewer should focus next and which local signals justified that focus

## `contract-repo-scale-lending-protocol`

Expected useful output:

- selected pack is `lending_protocol_benchmark_pack`
- bounded contract inventory lists the scoped protocol files
- local import graph connects `LendingPool.sol`, `OracleAdapter.sol`, and `ReserveVault.sol`
- entrypoint review lanes include collateral, liquidation, reserve, fee, or debt-accounting signals
- manual review queue and bounded confidence remain visible
- report avoids claiming a complete protocol audit or confirmed insolvency exploit

Evaluator pass signal:

- the report demonstrates repo-scale triage: it should show what files and lanes deserve human review first
