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
- provider-backed evaluation with your own configured API keys
- artifact review for sessions, traces, manifests, bundles, and replay inputs

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

## Benchmark Scorecard

Use the benchmark layer as a review checklist, not as a claim that the tool has
fully audited a target by itself.

| Area | What To Check | Stronger Signal |
| --- | --- | --- |
| Golden cases | Built-in ECC and smart-contract cases run cleanly and produce expected report shapes. | Stable smoke output across repeated local runs. |
| ECC coverage | Point formats, curve metadata, subgroup/cofactor checks, twist hygiene, curve-family transitions, and domain-completeness surfaces are visible in the report. | Local compute evidence and report interpretation agree without overstating confidence. |
| Smart-contract coverage | Parser, compile, inventory, repo map, casebook, benchmark pack, review queue, and residual-risk lanes appear when the input justifies them. | The report separates confirmed local signals from manual-review priorities. |
| Comparison | A saved baseline can be attached with `--compare-session`, `--compare-manifest`, or `--compare-bundle`. | Before/after lines show cautious deltas and possible regression flags. |
| Export quality | Session, trace, manifest, and bundle artifacts stay inside approved local export roots. | A reviewer can reproduce what was run and inspect the evidence trail. |
| Hosted path | Optional live smoke works only when the evaluator provides valid provider credentials. | Provider output is treated as interpretation, not proof. |

Scorecard misses are useful. If a lane is absent, the reviewer should check
whether the input did not justify that lane, the local toolchain was not
installed, the prompt was too narrow, or the project needs deeper coverage in
that area.

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

## Contact

- Email: `stelmak159@gmail.com`
- Telegram: `@ECDS4`
- Repository: `https://github.com/ECD5A/EllipticZero`
