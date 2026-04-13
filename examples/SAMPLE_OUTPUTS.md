# Sample Report Shapes

These are shortened, representative report shapes for safe evaluation. They show
the structure of useful output without claiming results for a real target. Real
reports depend on the local input, selected pack, configured tools, and available
evidence.

## ECC Benchmark Report

Command:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions for defensive ECC analysis."
```

Typical report areas:

```text
Research target:
- ECC curve/domain metadata, family transitions, and encoding assumptions.

Experiment pack:
- ecc_family_depth_benchmark_pack.

Evidence:
- curve parameter and metadata checks
- family transition benchmark steps
- point or encoding format review where applicable

Report focus:
- labels and aliases that require manual confirmation
- family-limited encoding assumptions
- missing or incomplete domain fields
- cautious comparison notes if a baseline is attached

Confidence:
- bounded by local tool evidence
- no cryptographic break claimed
- manual review required for production conclusions
```

Good output from this lane makes uncertainty visible. A useful run narrows what
to inspect next and keeps weak metadata signals separate from confirmed evidence.

## Smart-Contract Static Benchmark Report

Command:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

Typical report areas:

```text
Contract surface:
- parsed contract names, functions, modifiers, events, and visible state.

Static review lanes:
- externally reachable value flow
- low-level calls
- access-control surfaces
- upgrade or admin paths where present
- compiler or parser constraints

Benchmark pack summary:
- parse outline
- compile attempt
- surface mapping
- built-in pattern review
- optional external analyzer result if installed

Review queue:
- strongest lanes first
- residual risk lines
- exit criteria for follow-up review

Confidence:
- bounded first-pass static review
- manual audit, tests, invariants, and formal verification remain follow-up lanes
```

Good output from this lane should help an auditor prioritize review work. It
should preserve what was checked, what was not checked, and what still requires
manual confirmation.

## Repo-Casebook Report

Command:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
```

Typical report areas:

```text
Repo inventory:
- first-party contract files
- dependency or vendor scope
- entrypoint candidates
- function-family priorities

Casebook matches:
- asset-flow, vault/share, oracle/liquidation, governance/timelock, rewards,
  stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, or
  related lanes when supported by local evidence.

Triage:
- strongest matched case families
- unmatched or weakly matched lanes
- suggested manual review order

Confidence:
- casebook similarity is a prioritization signal
- it is not proof of a bug by itself
```

## Before/After Validation Report

Command:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the bounded audit and record before/after deltas against the saved baseline session."
```

Typical report areas:

```text
Comparison source:
- baseline session, manifest, or bundle path

Delta summary:
- changed review lanes
- added or removed pattern signals
- compile or parser posture changes
- benchmark pack differences where available

Regression watch:
- new unresolved lanes
- weaker evidence coverage
- missing artifacts or incomplete baseline context

Confidence:
- comparison is only as strong as the saved baseline and current run
- manual review remains required before release decisions
```

This lane is useful for hardening validation. It helps answer whether a later
run looks better, worse, or merely different under the same bounded review
model.
