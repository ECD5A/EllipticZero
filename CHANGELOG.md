# Changelog

All notable public changes for EllipticZero are summarized here.

The project currently follows a source-available release track under
`FSL-1.1-ALv2`. The package version is `0.1.0` until a tagged release line is
introduced.

## Unreleased

### Added

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
