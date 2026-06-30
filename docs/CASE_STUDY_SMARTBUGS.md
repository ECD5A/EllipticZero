# SmartBugs Reentrancy Case Study

This case study shows one reproducible EllipticZero review loop:

1. detect a labeled legacy reentrancy family in a pinned external dataset
2. preserve the local session and evidence
3. apply a bounded hardening example
4. compare the new run with the saved baseline
5. keep residual signals and manual-review limits visible

It is an evaluation example, not an exploitability proof or a completed audit.

## Target

| Field | Value |
| --- | --- |
| Dataset | [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) |
| Commit | `230e649123477eff332742a59a1c7cc6dc286cab` |
| Vulnerable source | `dataset/reentrancy/reentrancy_simple.sol` |
| Dataset label | `reentrancy` |
| Hardened control | `examples/case_studies/smartbugs_reentrancy/HardenedReentrancyVault.sol` |

EllipticZero does not vendor or execute the external dataset. The evaluator
clones the pinned revision and passes a local path to the project.

## Reproduce The Targeted Validation

```powershell
git clone --filter=blob:none --no-checkout https://github.com/smartbugs/smartbugs-curated.git .test_runs\smartbugs-curated
git -C .test_runs\smartbugs-curated fetch --depth 1 origin 230e649123477eff332742a59a1c7cc6dc286cab
git -C .test_runs\smartbugs-curated checkout --detach 230e649123477eff332742a59a1c7cc6dc286cab

python scripts\validate_smartbugs_subset.py `
  --dataset-root .test_runs\smartbugs-curated `
  --require-pinned-commit `
  --format markdown `
  --output .test_runs\smartbugs-validation.md
```

Observed on the pinned subset:

| Metric | Result | Support |
| --- | ---: | ---: |
| Recall | `100.00%` | 5 labeled positive cases |
| Miss rate | `0.00%` | 5 labeled positive cases |
| Targeted false-positive rate | `0.00%` | 1 synthetic negative control |
| Case result | `6/6` | 5 positives and 1 negative |

The false-positive rate applies only to the included synthetic control. It is
not a general estimate for arbitrary Solidity repositories.

## Run The Full Review

Run the vulnerable source through the normal EllipticZero session path:

```powershell
python -m app.main `
  --lang en `
  --domain smart_contract_audit `
  --contract-file .test_runs\smartbugs-curated\dataset\reentrancy\reentrancy_simple.sol `
  --pack contract_static_benchmark_pack `
  "Review the annotated legacy reentrancy case, preserve local evidence, and identify the minimum safe recheck."
```

Record the `Stored Session` path printed by the command. Then compare the local
hardening fixture with that baseline:

```powershell
python -m app.main `
  --lang en `
  --domain smart_contract_audit `
  --contract-file examples\case_studies\smartbugs_reentrancy\HardenedReentrancyVault.sol `
  --pack contract_static_benchmark_pack `
  --compare-session artifacts\sessions\<baseline-session>.json `
  "Recheck the hardened withdrawal path against the saved vulnerable baseline for reentrancy, post-call accounting, and unchecked low-level call signals."
```

Install the matching legacy compiler if compiler-backed checks are required:

```powershell
python scripts\bootstrap_smart_contract_toolchain.py --solc-version 0.4.15 --solc-version 0.8.24
```

## Observed Evidence

The vulnerable run produced local review signals for:

- reentrancy-adjacent sequencing in `withdrawBalance`
- accounting after the external value transfer
- unchecked legacy low-level call handling
- exact line hints around the withdrawal path

The hardened run:

- compiled successfully with Solidity `0.8.24`
- moved the accounting update before the external transfer
- added a nested-entry guard
- checked the low-level call result
- removed the targeted reentrancy, post-call accounting, and unchecked-call families

The saved baseline comparison reported two improvements, no regression-like
deltas, a reduction from six to two manual-review items, and a reduction from
four to zero priority findings. Confidence remained `manual_review_required`.

Slither still reported an informational `low-level-calls` item for the hardened
fixture. EllipticZero preserved that residual signal instead of treating the
before/after improvement as proof that the contract was fully safe.

## What This Demonstrates

This case demonstrates that EllipticZero can connect a labeled external case,
local detector evidence, an agent-structured report, a saved reproducibility
bundle, and a before/after recheck. It does not demonstrate complete SmartBugs
coverage, production exploitability, or the absence of other vulnerabilities.
