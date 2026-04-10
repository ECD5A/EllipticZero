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
