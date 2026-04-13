# Environment Profiles

EllipticZero can be evaluated in several runtime profiles. Start small, then add
hosted providers or local security tools only when you need them.

## Quick Matrix

| Profile | Best For | Required | Optional | Check |
|---|---|---|---|---|
| `mock` | first run, docs review, CLI walkthrough, reproducibility basics | Python 3.11+, project install | none | `python -m app.main --doctor` |
| `hosted-agent` | evaluating real agent reasoning with configured providers | Python 3.11+, provider API key | per-agent routing | `python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto` |
| `ecc-focused` | ECC metadata, encoding, subgroup, cofactor, and family-depth review | Python 3.11+, lab extras | SageMath | `python -m app.main --pack ecc_family_depth_benchmark_pack "Review ECC assumptions."` |
| `smart-contract-static` | Solidity/Vyper parse, compile, static review, and benchmark packs | Python 3.11+, smart-contract extras, managed `solc` | Slither, Foundry, Echidna | `.\scripts\setup_local_lab.ps1 -Profile smart-contract-static` |
| `repo-scale-audit` | protocol repository inventory, casebooks, review lanes, before/after comparison | smart-contract-static profile, local contract tree | Slither, Foundry, Echidna | `python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Review repo lanes."` |
| `full-local-lab` | broad local research across ECC, symbolic checks, smart-contract review, replay, and bundles | Python 3.11+, `.[lab]` extras | SageMath, Slither, Foundry, Echidna, hosted provider key | `.\scripts\setup_local_lab.ps1` |

## Profile Details

### `mock`

Use this profile when you want to evaluate the workflow without API keys.

What it gives you:

- deterministic local provider behavior
- CLI and interactive walkthroughs
- doctor/self-check
- local artifact generation
- replay and documentation validation

Useful commands:

```powershell
python -m app.main --doctor
python -m app.main --interactive
python -m app.main --list-packs
```

### `hosted-agent`

Use this profile when you want to evaluate real hosted model behavior. The
project supports `openai`, `openrouter`, `gemini`, and `anthropic` when the
corresponding API key is configured.

What it gives you:

- real agent reasoning instead of mock responses
- optional shared provider/model for all roles
- optional per-agent provider/model routing
- hosted smoke checks with timeout and request-token caps

Example:

```powershell
$env:OPENROUTER_API_KEY="local-key-here"
python -m app.main --provider openrouter "Review whether the local evidence is sufficient for this bounded research lead."
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

### `ecc-focused`

Use this profile for defensive ECC research. SageMath is useful when available,
but the core local path can still use the Python-installed lab dependencies.

What it gives you:

- curve metadata and registry checks
- point/public-key format inspection
- ECC consistency checks
- ECC family-depth, subgroup-hygiene, and domain-completeness benchmark packs
- cautious report sections for residual risk, review queue, and exit criteria

Useful commands:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions."
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, and twist-hygiene assumptions."
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review curve-domain completeness and registry assumptions."
```

### `smart-contract-static`

Use this profile for bounded smart-contract parsing, compile checks, static
review, and benchmark-pack runs.

What it gives you:

- Solidity/Vyper file or inline-code input
- parser and surface summaries
- managed Solidity compiler provisioning under `.ellipticzero/tooling/solcx`
- optional Slither, Foundry, and Echidna adapters when installed locally
- benchmark-pack summaries and review queues

Setup:

```powershell
.\scripts\setup_local_lab.ps1 -Profile smart-contract-static
```

Useful command:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

### `repo-scale-audit`

Use this profile when a contract file belongs to a larger local protocol tree.
EllipticZero can build a bounded inventory, derive review lanes, match casebook
families, and attach baseline comparisons.

What it gives you:

- first-party vs dependency scoping
- repo inventory and entrypoint review lanes
- protocol-style casebook matches
- function-family and risk-family prioritization
- before/after comparison with saved sessions, manifests, or bundles

Useful commands:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run and compare against the saved baseline."
```

### `full-local-lab`

Use this profile when you want the broadest local environment. It installs the
`lab` extra and provisions managed Solidity compiler versions unless skipped.

Setup:

```powershell
.\scripts\setup_local_lab.ps1
```

What to check after setup:

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m ruff check .
python -m compileall app tests scripts
pytest -q
```

## Optional Local Tools

EllipticZero degrades conservatively when optional tools are unavailable.
Missing tools should be visible in `doctor` output and report confidence notes
instead of being treated as successful evidence.

| Tool | Used For | Required By Default? |
|---|---|---|
| `solc` / managed `py-solc-x` | Solidity compile checks | managed path is provisioned by setup profiles |
| `slither` | external static-analysis adapter | optional |
| `forge` | Foundry-oriented local checks | optional |
| `echidna` | property/fuzz-oriented smart-contract checks | optional |
| `sage` | advanced symbolic and ECC math paths | optional |

## Provider Keys

Hosted providers are optional. Do not commit API keys.

Supported environment variables:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Use `.env.example` as a template for local configuration.
