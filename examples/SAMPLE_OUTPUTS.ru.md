# Примеры форм отчёта

Это сокращённые примеры структуры отчёта для безопасной оценки проекта. Они
показывают форму полезного вывода без заявлений о реальной цели. Реальные отчёты
зависят от локального входа, выбранного pack, настроенных инструментов и
доступной доказательной базы.

## Короткие case-study snapshots

Это короткие примеры для оценки проекта. Они описывают, что проверяющий должен
увидеть в результате запуска, а не заявляют находку в реальной цели.

### Смарт-контракт: vault permission lane

Форма входа:

- один vault-style контракт с externally reachable value-flow, permission,
  share/accounting или signature-adjacent поверхностями
- ожидаемый маршрут: `vault_permission_benchmark_pack`

Что должен увидеть проверяющий:

- разобранные функции, состояние, модификаторы и value-flow поверхности
- короткая review queue с самыми сильными lanes в начале
- residual-risk и exit-criteria строки для ручной проверки
- pattern evidence отделена от заявлений о подтвержденной эксплуатации

### Смарт-контракт: repo-scale lending protocol

Форма входа:

- небольшой протокольный репозиторий с pool, oracle и reserve/vault компонентами
- ожидаемый маршрут: `lending_protocol_benchmark_pack`

Что должен увидеть проверяющий:

- scoped contract inventory и import graph
- collateral, liquidation, reserve, fee, oracle или debt-accounting review lanes,
  если они поддержаны локальной доказательной базой
- casebook/benchmark posture и первые приоритеты ручной проверки
- нет заявления о полном аудите протокола или подтвержденной insolvency-уязвимости

### ECC: проверка пограничных форматов точки

Форма входа:

- secp256k1-focused seed про префикс точки, compressed/uncompressed encoding и
  локальные проверки согласованности
- ожидаемый маршрут: `point_format_inspection_pack`

Что должен увидеть проверяющий:

- point-format evidence показана как локальная доказательная база
- malformed или edge-format наблюдения остаются сигналами для review
- уверенность остаётся ограниченной, без заявлений о key recovery или взломе
  промышленной библиотеки

## Smart-contract static benchmark-отчёт

Команда:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

Типичные области отчёта:

```text
Contract surface:
- parsed contract names, functions, modifiers, events, and visible state.

Static review lanes:
- externally reachable value flow
- low-level calls
- access-control surfaces
- upgrade or admin paths where present
- compiler or parser constraints

Benchmark pack summary:
- parse outline
- compile attempt
- surface mapping
- built-in pattern review
- optional external analyzer result if installed

Review queue:
- strongest lanes first
- residual risk lines
- exit criteria for follow-up review

Confidence:
- bounded first-pass static review
- manual audit, tests, invariants, and formal verification remain follow-up lanes
```

Хороший вывод в этой линии помогает аудитору расставить приоритеты. Он должен
сохранять, что было проверено, что не было проверено и что требует ручного
подтверждения.

## Repo-casebook отчёт

Команда:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
```

Типичные области отчёта:

```text
Repo inventory:
- first-party contract files
- dependency or vendor scope
- entrypoint candidates
- function-family priorities

Casebook matches:
- asset-flow, vault/share, oracle/liquidation, governance/timelock, rewards,
  stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, or
  related lanes when supported by local evidence.

Triage:
- compact repo triage snapshot with the top lane, top files, why it matters,
  and next manual step
- strongest matched case families
- unmatched or weakly matched lanes
- suggested manual review order

Confidence:
- casebook similarity is a prioritization signal
- it is not proof of a bug by itself
```

## Before/after validation отчёт

Команда:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the bounded audit and record before/after deltas against the saved baseline session."
```

Типичные области отчёта:

```text
Comparison source:
- baseline session, manifest, or bundle path

Delta summary:
- compact remediation-delta summary with before/after posture, strongest
  improvement or regression, and next replay path
- changed review lanes
- added or removed pattern signals
- compile or parser posture changes
- benchmark pack differences where available

Regression watch:
- new unresolved lanes
- weaker evidence coverage
- missing artifacts or incomplete baseline context

Confidence:
- comparison is only as strong as the saved baseline and current run
- manual review remains required before release decisions
```

Эта линия полезна для проверки защитных доработок. Она помогает понять, стал ли
новый запуск лучше, хуже или просто отличается в рамках той же ограниченной
модели проверки.

## ECC benchmark-отчёт

Команда:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions for defensive ECC analysis."
```

Типичные области отчёта:

```text
Research target:
- ECC curve/domain metadata, family transitions, and encoding assumptions.

Experiment pack:
- ecc_family_depth_benchmark_pack.

Evidence:
- curve parameter and metadata checks
- family transition benchmark steps
- point or encoding format review where applicable

Report focus:
- labels and aliases that require manual confirmation
- family-limited encoding assumptions
- missing or incomplete domain fields
- cautious comparison notes if a baseline is attached

ECC triage snapshot:
- primary ECC family
- current support labels
- next ECC check

Confidence:
- bounded by local tool evidence
- no cryptographic break claimed
- manual review required for production conclusions
```

Хороший вывод в этой линии показывает неопределённость. Полезный запуск сужает
следующий маршрут проверки и отделяет слабые сигналы по метаданным от
подтверждённой доказательной базы.
