# Changelog

All notable public changes for EllipticZero are summarized here.

The project currently follows a source-available release track under
`FSL-1.1-ALv2`. The current package version is `0.1.2`.

## Unreleased

### Added

- Final CLI reports now include the exact saved-run evaluation command whenever
  a reproducibility bundle was produced.

## 0.1.2 - 2026-04-21

### Added

- `report_snapshot_summary` and `report_snapshot_count` in manifests and bundle
  overviews so compact ECC / smart-contract triage and remediation-delta signals
  are visible without opening the full session JSON.
- `--evaluation-summary --replay-session/--replay-manifest/--replay-bundle`
  mode for compact reviewer summaries of saved runs without re-execution.
- Saved-run evaluation summaries now include a `review_status` block with
  evidence depth, comparison readiness, missing artifacts, and manual-review
  posture.

## 0.1.1 - 2026-04-15

### Added

- Machine-readable `--evaluation-summary --evaluation-summary-format json`
  output for evaluator and integration workflows.
- Smart-contract finding cards that connect bounded potential issues to
  evidence, risk context, defensive fix direction, and a recheck path.
- Evidence-coverage summaries, toolchain fingerprints, and secret-redaction
  summaries in reports, manifests, bundle overviews, and export notes.
- Secret redaction for saved session JSON, trace JSONL, comparative-report, and
  bundle JSON snapshots before export.
- Buyer-demo guidance for the no-key vault/permission golden case.
- More compact smart-contract finding-card text for first-screen review.
- Compact `--evaluation-summary` CLI path for no-key evaluator orientation.
- Evaluator-facing case-study snapshots for ECC point-format review,
  vault-permission review, and repo-scale lending-protocol triage.

## 0.1.0 - 2026-04-13

Initial public FSL release track.

### Added

- Local-first bounded research workflow for ECC and smart-contract audit.
- Orchestrated agent roles: Orchestrator, Math, Cryptography, Strategy,
  Hypothesis, Critic, and Report.
- Reproducible session artifacts, traces, manifests, bundles, replay, and
  doctor/self-check paths.
- ECC benchmark depth for point formats, curve metadata, aliases, curve-family
  transitions, subgroup/cofactor hygiene, twist hygiene, and bounded
  domain-completeness checks.
- Smart-contract repo-scale audit layer with parser, compile, inventory,
  first-party/dependency scoping, protocol maps, entrypoint lanes,
  function-family priorities, casebook matching, benchmark packs, and
  before/after comparison support.
- Golden/synthetic evaluator cases for stable ECC and smart-contract smoke
  checks.
- Provider configuration for `mock`, `openai`, `openrouter`, `gemini`, and
  `anthropic`, with live smoke checks available when a user supplies their own
  keys.
- Buyer-facing documentation for licensing, commercial use, environment
  profiles, use cases, sample outputs, and evaluation.
- GitHub issue templates, pull-request template, tests workflow, CodeQL
  workflow, Dependabot configuration, and security policy.

### Security And Safety

- Bounded local plugin loading rules.
- Export-root filtering for reproducibility manifests and bundles.
- Report language that keeps local evidence, model interpretation, confidence,
  residual risk, and manual-review boundaries separate.
- Responsible-use and private vulnerability-reporting documentation.

### Licensing

- Public source-available licensing under `FSL-1.1-ALv2`.
- Apache License 2.0 future-license transition for each published version on
  the second anniversary of that version becoming available.
- Separate commercial-license guidance for competing commercial use, hosted or
  managed service use, SaaS/platform deployment, OEM, white-label, resale, and
  similar product scenarios.
