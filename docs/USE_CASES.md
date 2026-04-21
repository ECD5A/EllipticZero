# EllipticZero Use Cases

EllipticZero is built for teams and researchers who need bounded local
investigation, reproducible evidence, and cautious reports across ECC and
smart-contract audit workflows.

This page describes where the project is useful, how to evaluate it, and which
strengths matter most for research, audit, and commercial review.

## Primary Users

- independent security researchers who want a local audit lab with replayable artifacts
- protocol teams that need a bounded first-pass review before deeper manual audit
- internal security teams comparing before/after hardening results
- cryptography engineers reviewing ECC metadata, encoding, subgroup, or domain assumptions
- smart-contract auditors who want structured triage, casebook matching, and report scaffolding
- organizations evaluating controlled multi-agent research workflows

## Useful Scenarios

- turn a vague ECC or smart-contract research idea into a bounded local session
- preserve agent reasoning, local tool evidence, trace files, manifests, and reports together
- compare a fresh run against a saved baseline session, manifest, or bundle
- run benchmark packs for ECC family-depth, subgroup hygiene, and domain completeness
- run benchmark packs for smart-contract static review, repo-scale casebooks, and protocol archetypes
- evaluate the product with safe golden cases before using private repositories
- build a first-pass review queue with compact triage snapshots, manual-review lanes, and cautious confidence notes
- keep hosted-provider usage optional while preserving mock-mode reproducibility

## Buyer-Relevant Strengths

- local-first design keeps sensitive inputs away from a default hosted service path
- bounded orchestration keeps agent work inside a controlled review loop
- reports preserve negative, null, inconclusive, and manual-review outcomes
- report snapshots compress repo-scale, ECC, and remediation deltas into first-screen review cues
- benchmark packs make repeated review paths easier to compare over time
- before/after comparison supports hardening validation and regression checks
- source-available licensing keeps evaluation possible while preserving a commercial path

## What To Evaluate First

1. Run `python -m app.main --doctor`.
2. Run `python -m app.main --list-packs`.
3. Run the [golden cases runbook](../examples/golden_cases/RUNBOOK.md).
4. Run one ECC benchmark pack in `mock` mode.
5. Run one smart-contract static or repo-scale benchmark pack on a small local contract tree.
6. Save the generated artifacts and replay the session.
7. Attach a baseline with `--compare-session` and check whether the report preserves deltas cautiously.
8. Review the limitations and manual-review lanes before treating any finding as actionable.

For setup choices, see [Environment Profiles](ENVIRONMENT_PROFILES.md).

## Commercial Fit

EllipticZero may be commercially interesting when the buyer needs:

- private local review workflows for smart-contract repositories
- reproducible audit evidence rather than one-off chat output
- ECC and smart-contract research under one bounded orchestration model
- configurable hosted providers without making hosted execution mandatory
- benchmark-oriented comparison across historical sessions or hardening passes

Competing commercial use, hosted deployment, OEM distribution, managed-service
use, white-label use, or resale may require a separate commercial agreement.
The license files are the source of truth.

## Strengths In Practice

EllipticZero is strongest when it is used to:

- turn broad research leads into bounded, reviewable sessions
- keep useful audit context together instead of losing it in chat history
- make evidence, uncertainty, and confidence visible in the same report
- compare hardening passes against saved baselines
- give reviewers a clearer first-pass queue before deeper expert work
- preserve a local-first workflow while still allowing configured hosted providers

## How To Read Results

The strongest output is a reproducible evidence trail with cautious next steps.
Reports are designed to support qualified review: they preserve what was checked,
what changed, what remains uncertain, and which lanes deserve the next human
look before security, financial, or deployment decisions.
