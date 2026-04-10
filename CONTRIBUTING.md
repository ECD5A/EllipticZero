# Contributing

## Scope

This guide explains how to contribute without weakening the project's core constraints. Contributions are welcome, but the project should remain:

- local-first
- sandboxed
- reproducible
- evidence-first
- simple from the user's point of view

If a change makes the system noisier, more contradictory, or closer to an unrestricted execution shell, it is probably the wrong direction.

## Read First

Before changing code, read:

- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `REPRODUCIBILITY.md`
- `REPORT_SPEC.md`
- `SECURITY.md`

## Product Direction

The intended user flow is simple:

1. choose language
2. choose a research domain
3. optionally choose a curve or provide contract input
4. enter a free-form research idea
5. run the session
6. review evidence and the cautious report

Internal complexity should stay inside the orchestrator, agent loop, sandbox policies, local runners, and reproducibility layers.

## High-Value Contribution Areas

- sandboxed local research runners
- bounded ECC testbeds and synthetic targets
- smart-contract audit runners, corpora, repo-casebooks, and report quality
- multi-agent research quality
- reproducibility, traces, replay, and manifests
- cautious reporting quality
- clarity of docs and setup

Lower-priority areas should not dominate the roadmap:

- cosmetic UI churn
- feature sprawl in advanced/internal screens
- speculative ranking logic
- anything that weakens sandbox boundaries

## Safety Rules

Please keep these boundaries intact:

- no arbitrary execution from agent prompts
- no direct shell access for reasoning agents
- no hidden remote execution paths
- no silent weakening of traceability or replayability
- no exaggerated claims in reports without evidence

Local computation should remain controlled by approved tools, runners, and policies.

## Local Setup And Tests

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .[lab]
.\.venv\Scripts\python.exe -m compileall app tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Windows may emit a `PytestCacheWarning` if `.pytest_cache` is blocked by local policy. That warning is not, by itself, a logic failure.

## Documentation Synchronization

English documentation is authoritative.

Required English-to-Russian mapping:

- `README.md` -> `README.ru.md`
- `ARCHITECTURE.md` -> `docs/ru/ARCHITECTURE.ru.md`
- `AGENTS.md` -> `docs/ru/AGENTS.ru.md`
- `COMMERCIAL_LICENSE.md` -> `docs/ru/COMMERCIAL_LICENSE.ru.md`
- `REPRODUCIBILITY.md` -> `docs/ru/REPRODUCIBILITY.ru.md`
- `REPORT_SPEC.md` -> `docs/ru/REPORT_SPEC.ru.md`
- `SECURITY.md` -> `docs/ru/SECURITY.ru.md`
- `LICENSE_TRANSITION.md` -> `docs/ru/LICENSE_TRANSITION.ru.md`
- `TRADEMARKS.md` -> `docs/ru/TRADEMARKS.ru.md`
- `CONTRIBUTING.md` -> `docs/ru/CONTRIBUTING.ru.md`

If an English file above changes, update the mapped Russian file in the same change.

## Pull Request Expectations

A good change usually includes:

- a clear problem statement
- a bounded implementation
- tests
- updated docs when user-facing behavior changes
- a short note on architectural impact

When relevant, mention sandbox implications, reproducibility implications, and whether the change affects standard mode, exploratory mode, or both.

## Contribution Licensing

Before submitting a substantial contribution, please open an issue and discuss
the proposed change first.

By submitting a contribution, you agree that the contribution is provided under
the repository license and that the maintainer may request additional
contributor paperwork for larger changes if it becomes necessary for future
licensing, commercial distribution, or project governance.

Do not submit code unless you have the right to contribute it.

Major contributions should be made only by prior agreement with the maintainer.
