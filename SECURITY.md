# Security Policy

## Scope

This policy covers security issues that matter most for the repository, especially when they involve:

- sandbox boundary failures
- arbitrary or uncontrolled execution paths
- unsafe tool or runner escapes
- trace, bundle, replay, or artifact disclosure issues
- provider-key handling mistakes
- reproducibility flaws that create real exposure

This repository is not intended for public exploit release workflows.

Unsafe local plugin path layouts, symlinks, or out-of-root plugin files are expected to fail bounded local safety checks rather than load into the registry. Reproducibility manifests and bundles are also expected to filter artifact references that resolve outside the approved local storage roots, and session/trace copies should stay inside those same approved roots before they are exported.

## Reporting

Please do not publish unconfirmed security issues as public GitHub issues.

Preferred contact flow:

1. Use GitHub private vulnerability reporting if it is enabled for the repository.
2. If that is not available, contact the maintainer at `stelmak159@gmail.com`.
3. If no private channel exists yet, open a minimal public issue asking for a secure contact path without posting sensitive details.

## What To Include

Please include:

- affected version or commit
- operating system and Python version
- exact reproduction steps
- whether the issue requires non-default configuration
- whether it affects `mock`, external providers, or both
- whether it breaks the sandbox or only a reporting surface
- whether local artifacts, traces, bundles, or secrets are exposed

If possible, include a minimal reproducible case that stays within the repository's defensive and sandboxed scope.

## Responsible Use And Liability

EllipticZero is provided for authorized, sandboxed, defensive cryptography research and smart-contract audit research.

By using this project, you accept that:

- you are responsible for how you use the software, its outputs, and any derived workflows
- you must comply with applicable law, policy, contract, export controls, and institutional review requirements
- you must only use the project in environments, systems, datasets, and research contexts that you own or are explicitly authorized to assess
- you must keep substantive experiments bounded, inspectable, reversible, and reproducible

EllipticZero is distributed on an `AS IS` basis, without warranties or guarantees of fitness for any particular purpose. Maintainers and contributors are not responsible for misuse, unauthorized activity, downstream damage, data loss, regulatory violations, or conclusions drawn from incomplete evidence.

## Current Boundaries

EllipticZero is intentionally designed so that:

- agents are reasoning-only
- local execution happens only through approved runners and tools
- research stays local-first and sandboxed
- outputs remain inspectable and reproducible

Reports that show a violation of those boundaries are especially valuable.

## Trust And Data Boundary

EllipticZero treats the user seed, agent reasoning, local tools, artifacts, and
human review as different trust layers. Agent output is interpretation. Local
tool outputs, saved sessions, traces, manifests, bundles, and reviewer judgment
carry the evidence trail.

The default provider is `mock`, which is deterministic and does not require API
keys. This path is intended for first evaluation, golden cases, documentation
checks, and reproducibility smoke tests.

Hosted providers are optional. Configure `openai`, `openrouter`, `gemini`, or
`anthropic` only when you intentionally want live model output instead of the
default `mock` path. When a hosted provider is used, prompts and bounded context
needed for the agent call may be sent to that provider according to the
provider's own terms.

Do not use a hosted provider for private contracts, proprietary code, client
material, or sensitive traces unless that sharing is acceptable for your
organization. The live-smoke command verifies provider connectivity only; it
does not prove audit quality, privacy posture, or production readiness.

Before a live hosted-provider run, preview the prepared context:

```powershell
python -m app.main --provider openrouter --provider-context-preview "Review provider privacy before running live agents."
```

For private contract review, run the preview with the same contract and routing
flags you plan to use. The preview does not call the provider.

EllipticZero does not claim OS-grade isolation, malware containment, or safe
execution of arbitrary untrusted programs. Evaluate hostile targets in an
environment you already trust for that purpose.

## Artifact, SARIF, And Claim Boundary

Saved session and trace snapshots apply secret redaction for likely credentials,
but reviewers should still avoid placing secrets in prompts, contract comments,
local paths, environment dumps, or artifacts.

SARIF export is a CI and Code Scanning bridge for saved runs:

```powershell
python -m app.main --replay-bundle .\artifacts\bundles\session_id --export-sarif .\artifacts\sarif\session_id.sarif
```

SARIF results are review items, not vulnerability proof. A local signal is not
automatically a confirmed vulnerability, a finding card is not a final audit
verdict, and a benchmark pass is not complete coverage. If evidence is
insufficient, the correct outcome is manual review, inconclusive status, or a
narrower follow-up.
