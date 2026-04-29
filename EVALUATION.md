# Evaluating EllipticZero

This guide is for researchers, security teams, integrators, and potential
commercial partners who want to evaluate EllipticZero without guessing what to
run first.

EllipticZero is designed to be inspected directly: source code, documentation,
CLI behavior, local artifacts, reports, benchmark packs, and golden cases should
all tell the same story.

## What You Can Evaluate

Under the public `FSL-1.1-ALv2` license terms, the public repository can be
reviewed, built, tested locally, and evaluated for research, internal review,
and other permitted purposes.

Useful evaluation paths include:

- source review of the orchestration, agent roles, runners, report shaping, and
  export boundaries
- no-key CLI evaluation in `mock` mode
- golden/synthetic evaluator cases for stable smoke checks
- ECC benchmark-pack review across point formats, curve metadata, subgroup,
  cofactor, twist, and domain-completeness surfaces
- smart-contract audit review across parser, compile, repo inventory,
  casebook, benchmark, comparison, and manual-review lanes
- known-case profile review using cached metadata from allowlisted sources;
  profiles guide local checks and never execute remote code
- provider-backed evaluation with your own configured API keys
- artifact review for sessions, traces, manifests, bundles, and replay inputs
- SARIF export from saved runs for CI or GitHub Code Scanning review

`mock` mode is the easiest starting point, not the only evaluation path.

## Fast No-Key Path

Install the lab profile:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[lab]
```

Check the local environment:

```powershell
python -m app.main --doctor
```

Print the compact evaluator summary:

```powershell
python -m app.main --evaluation-summary
```

Machine-readable evaluator summary:

```powershell
python -m app.main --evaluation-summary --evaluation-summary-format json
```

For a saved run, print a compact reviewer summary without re-executing:

```powershell
python -m app.main --evaluation-summary --replay-bundle .\artifacts\bundles\session_id
```

Saved-run summaries include a short `review_status` block with evidence depth,
comparison readiness, missing reviewer artifacts, and manual-review posture.

Export saved-run review items to SARIF:

```powershell
python -m app.main --replay-bundle .\artifacts\bundles\session_id --export-sarif .\artifacts\sarif\session_id.sarif
```

SARIF output is intended for CI and Code Scanning review. It preserves
`reviewRequired=true` because bounded signals still require local evidence and
human review before they become confirmed findings.

Export a saved-run Markdown report:

```powershell
python -m app.main --replay-bundle .\artifacts\bundles\session_id --export-report-md .\artifacts\reports\session_id.md
```

Markdown reports are for review, sharing, and archive. They intentionally avoid
embedding the full seed or contract source; the session, trace, manifest, bundle,
and local tool outputs remain the evidence trail. The top review snapshot shows
the primary signal, next review step, evidence posture, and residual risk when
the saved run contains those fields.

For the menu-first path, run the interactive console and choose
`EXPORT REVIEW FILES` after a session completes. It writes `report.md` and
`review.sarif` into the session bundle without requiring export flags.

The same interactive console also exposes `EVALUATION LAB` for no-key
review paths: golden cases, experiment packs, project or saved-run summaries,
baseline comparison, known-case metadata, and provider context preview.

Preview hosted-provider context before a live agent run:

```powershell
python -m app.main --provider openrouter --provider-context-preview "Review provider privacy before running live agents."
```

For private contract review, run the preview with the same `--domain`,
`--contract-file`, `--contract-root`, `--pack`, and provider flags you plan to
use. The preview does not call the provider.

List built-in golden cases:

```powershell
python -m app.main --list-golden-cases
```

Run an ECC golden case:

```powershell
python -m app.main --golden-case ecc-secp256k1-point-format-edge
```

Run a repo-scale smart-contract golden case:

```powershell
python -m app.main --golden-case contract-repo-scale-lending-protocol
```

## Buyer Demo Path

For the fastest product-oriented review, run the vault/permission golden case:

```powershell
python -m app.main --golden-case contract-vault-permission-lane
```

In the first screen of the report, check for:

- `Finding Cards` with potential finding, evidence, why it matters, fix direction, and recheck path
- `Evidence Coverage` showing evidence count, tool-backed count, tools, experiment types, and review items
- reproducibility outputs for session, trace, comparative report, and bundle
- `Toolchain Fingerprint` and `Secret Redaction` in the lower export-quality section

This path is intentionally no-key and synthetic. It demonstrates the workflow
shape a commercial reviewer should expect before testing a private repository.

## Benchmark Scorecard

Use the benchmark layer as a review checklist, not as a claim that the tool has
fully audited a target by itself.

| Area | What To Check | Stronger Signal |
| --- | --- | --- |
| Golden cases | Built-in ECC and smart-contract cases run cleanly and produce expected report shapes. | Stable smoke output across repeated local runs. |
| ECC coverage | Point formats, curve metadata, subgroup/cofactor checks, twist hygiene, curve-family transitions, and domain-completeness surfaces are visible in the report. | Local compute evidence and report interpretation agree without overstating confidence. |
| Smart-contract coverage | Parser, compile, inventory, repo map, casebook, benchmark pack, review queue, signature, oracle, upgrade, token-accounting, and residual-risk lanes appear when the input justifies them. | The report separates confirmed local signals from manual-review priorities. |
| Local analyzer evidence | Optional Slither output is normalized with severity and source locations; Foundry projects can add local build/test evidence when `foundry.toml` is present. | External analyzer signals are tied to report priorities without being treated as proof by themselves. |
| Known-case metadata | `EVALUATION LAB` -> `KNOWN CASES` can update or inspect cached metadata profiles from allowlisted sources. | The report shows known-case matches only as context or local-signal-backed review items, not as automatic exploit claims. |
| Comparison | A saved baseline can be attached with `--compare-session`, `--compare-manifest`, or `--compare-bundle`. | Before/after lines show cautious deltas and possible regression flags. |
| Export quality | Session, trace, manifest, bundle, and `report.md` artifacts stay inside approved local export roots. | A reviewer can reproduce the run, inspect the evidence trail, and share a Markdown report. |
| CI review | Saved runs can export SARIF 2.1.0 review items. | Code Scanning can display bounded findings without treating them as automatic proof. |
| Provider privacy | `--provider-context-preview` is run before live hosted agents. | The reviewer can see whether contract code or source paths may be sent to hosted routes. |
| Hosted path | Optional live smoke works only when the evaluator provides valid provider credentials. | Provider output is treated as interpretation, not proof. |

Scorecard misses are useful. If a lane is absent, the reviewer should check
whether the input did not justify that lane, the local toolchain was not
installed, the prompt was too narrow, or the project needs deeper coverage in
that area.

## Benchmark Evidence Checklist

Useful benchmark evidence should show:

- the exact command that was run
- the selected domain and benchmark pack
- local tool outputs or saved artifacts
- report anchors that match the expected shape
- confidence and manual-review boundaries
- replay, saved-run summary, Markdown report, or SARIF review paths
- a clear distinction between local evidence and model interpretation

The built-in golden cases are safe synthetic checks for report shape, pack
routing, and evidence boundaries:

| Case | Domain | Expected Review Focus |
| --- | --- | --- |
| `ecc-secp256k1-domain-completeness` | ECC | Curve-domain assumptions, metadata completeness, bounded confidence. |
| `ecc-25519-subgroup-hygiene` | ECC | Subgroup/cofactor, twist hygiene, encoding caveats. |
| `ecc-secp256k1-point-format-edge` | ECC | Point-format inspection and parser/encoding boundaries. |
| `contract-vault-permission-lane` | Smart contracts | Vault permissions, externally reachable value flow, finding cards. |
| `contract-reentrancy-review-lane` | Smart contracts | External-call ordering, withdrawal accounting, and reentrancy-adjacent review lanes. |
| `contract-governance-timelock-lane` | Smart contracts | Governance, timelock, upgrade-control, and emergency-lane review. |
| `contract-repo-scale-lending-protocol` | Smart contracts | Repo inventory, protocol lanes, liquidation/collateral/accounting review. |

Missing sections are useful too. They can mean the input did not justify that
lane, the selected pack was too narrow, the local toolchain was not installed,
or the report stayed cautious because evidence was insufficient.

## Smart-Contract Repo-Scale Path

For a local contract repository, start with a bounded run:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for externally reachable value flow, admin controls, and repo-scale review lanes."
```

Then compare against a saved baseline when validating a change:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the bounded audit and record before/after deltas against the saved baseline session."
```

What to inspect:

- contract inventory and repo-scale protocol map
- entrypoint review lanes
- function-family priorities
- casebook and benchmark coverage
- strongest priorities and residual-risk lines
- compile status and external analyzer posture when local tools are installed
- before/after deltas and regression flags when comparison input is provided

## ECC Path

For ECC-focused evaluation, review the routing and packs first:

```powershell
python -m app.main --show-routing
python -m app.main --list-packs
```

Then run a bounded ECC prompt:

```powershell
python -m app.main "Inspect whether secp256k1 point encoding, curve metadata, and local consistency checks produce review-worthy defensive signals."
```

What to inspect:

- curve and family coverage
- point-format and domain-parameter handling
- subgroup/cofactor and twist-hygiene signals
- local compute evidence versus agent interpretation
- confidence calibration and manual-review boundaries
- benchmark posture and regression-watch lines

## Provider-Backed Evaluation

Hosted providers are optional. Configure a provider only when you want to test
the agent loop with live model output instead of the default `mock` provider.

Supported provider names:

- `openai`
- `openrouter`
- `gemini`
- `anthropic`
- `mock`

Run a bounded live smoke only with your own key:

```powershell
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

Provider-backed evaluation should still be judged by local evidence,
artifacts, report boundaries, and reproducibility posture. Model output alone
is not treated as proof.

## What Good Evaluation Looks Like

A useful evaluation should answer:

- Can the project run cleanly in a local environment?
- Are generated reports cautious and evidence-linked?
- Do benchmark and golden cases produce stable, reviewable output?
- Are smart-contract repo-scale signals separated from manual-review claims?
- Are ECC signals bounded by local compute and explicit uncertainty?
- Are artifacts and exports reproducible enough for review?
- Are commercial boundaries clear before product, hosted, OEM, white-label, or
  resale use?

## Commercial Boundary

Evaluation, research, internal review, and local testing are welcome under the
public license terms.

If your use case involves competing commercial use, hosted or managed service
use, SaaS/platform deployment, OEM distribution, white-label usage, resale, or
commercial security-platform integration, contact before shipping, selling, or
deploying.

See:

- [LICENSE](LICENSE)
- [LICENSE_FAQ.md](LICENSE_FAQ.md)
- [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)
- [LICENSE_TRANSITION.md](LICENSE_TRANSITION.md)
- [SECURITY.md](SECURITY.md)

## Contact

- Email: `stelmak159@gmail.com`
- Telegram: `@ECDS4`
- Repository: `https://github.com/ECD5A/EllipticZero`
