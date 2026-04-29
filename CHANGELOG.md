# Changelog

All notable public changes for EllipticZero are summarized here.

The project follows a source-available release track under `FSL-1.1-ALv2`.
Package version: `0.1.5`.

## Unreleased

### Added

- Added interactive smart-contract folder input: the console can accept a local
  contract directory, select a representative Solidity/Vyper file, and preserve
  the scoped contract root for repo-scale review.
- Added `contract-reentrancy-review-lane`, a safe synthetic golden case for
  external-call ordering, withdrawal accounting, and reentrancy-adjacent review
  lanes.

### Changed

- Shifted public positioning toward smart-contract audit first, with defensive
  ECC research as the second supported domain.

## 0.1.5 - 2026-04-29

### Added

- Added a lightweight known-case threat-intel layer: allowlisted SmartBugs
  metadata and Slither detector-family profiles can be cached locally, matched
  against smart-contract review signals, and shown in reports without executing
  remote code.
- Added `KNOWN CASES` to the interactive evaluation lab for updating profiles,
  inspecting the local cache, and reviewing allowed metadata sources.
- Added deeper bounded smart-contract review signals for signature domain
  separation, Chainlink-style oracle answer bounds, and immediate upgrade paths
  that lack an explicit delay, queue, or governance control.
- Added token balance-delta and oracle decimal-scaling review signals for
  fee-on-transfer style accounting and price-precision checks.
- Added matching built-in corpus cases for token balance-delta and oracle
  decimal-scaling review so the new families are covered by local benchmark
  sweeps.
- Added richer Slither/Foundry evidence ingestion: Slither findings now keep
  normalized severity and source-location summaries, while Foundry projects can
  contribute local `forge test` results when `foundry.toml` is present.

### Changed

- Moved `EVALUATION LAB` to the main interactive menu and renamed the former
  advanced area to `SYSTEM / TOOLS` to reduce nested navigation.

## 0.1.4 - 2026-04-28

### Added

- Added saved-run Markdown report export through `--export-report-md`.
- Added a compact review snapshot near the top of console and Markdown reports.
- Added clearer mock-mode onboarding: localized validation errors, semantic-light
  seed validation, compact seed examples, and boxed console summaries.
- Added a post-run session-actions menu for one-step `report.md` and
  `review.sarif` export.
- Added an interactive `EVALUATION LAB` menu for golden cases,
  experiment packs, project or saved-run summaries, baseline comparison, and
  provider context preview.
- Added `report.md` to reproducibility bundles when a session report is
  available. JSON evidence artifacts remain the source of truth.

## 0.1.3 - 2026-04-26

### Added

- Final CLI reports include the exact saved-run evaluation command whenever a
  reproducibility bundle is produced.
- Added SARIF 2.1.0 saved-run review output for CI and
  GitHub Code Scanning workflows.
- SARIF results include stable partial fingerprints, tags, and EllipticZero
  severity metadata for cleaner CI triage.
- Added a provider context preview CLI path so hosted-provider runs can be
  reviewed for possible context exposure before any live model call.
- Expanded the existing evaluation and security guides with provider privacy,
  sandbox limits, artifact boundaries, golden cases, and SARIF review checks.

## 0.1.2 - 2026-04-21

### Added

- `report_snapshot_summary` and `report_snapshot_count` in manifests and bundle
  overviews so compact ECC / smart-contract triage and remediation-delta signals
  are visible without opening the full session JSON.
- `--evaluation-summary --replay-session/--replay-manifest/--replay-bundle`
  mode for compact reviewer summaries of saved runs without re-execution.
- Saved-run evaluation summaries include a `review_status` block with evidence
  depth, comparison readiness, missing artifacts, and manual-review posture.

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
