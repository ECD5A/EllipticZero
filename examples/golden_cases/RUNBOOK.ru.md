# Runbook для golden cases

Используй этот runbook, если нужно быстро оценить EllipticZero без приватного
клиентского кода и без live provider keys.

## 1. Проверить локальную готовность

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m app.main --list-golden-cases
```

Хороший сигнал для оценки:

- CLI запускается
- benchmark-пакеты отображаются
- golden cases отображаются
- отсутствующие опциональные инструменты показаны явно, а не спрятаны

Самый короткий прямой запуск:

```powershell
python -m app.main --golden-case ecc-secp256k1-point-format-edge
python -m app.main --golden-case contract-repo-scale-lending-protocol
```

## 2. Запустить ECC domain completeness

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether secp256k1 curve-domain assumptions are complete enough for cautious defensive reporting."
```

Смотреть:

- выбранный пакет и выполненные шаги пакета
- curve-domain metadata
- ограниченную уверенность и границы ручной проверки

## 3. Запустить ECC point-format edge

```powershell
python -m app.main --pack point_format_inspection_pack "Inspect a compressed secp256k1 public-key encoding edge and keep format evidence separate from stronger cryptographic claims."
```

Смотреть:

- format или prefix evidence
- bounded consistency output
- отсутствие заявлений про private-key recovery или exploit

## 4. Запустить single-contract smart-contract cases

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticVault.sol --pack vault_permission_benchmark_pack "Benchmark vault share-accounting, permission, and externally reachable value-flow review lanes."
```

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticGovernanceTimelock.sol --pack governance_timelock_benchmark_pack "Benchmark governance timelock, upgrade-control, and emergency-lane review surfaces."
```

Смотреть:

- parser и surface output
- manual review queue
- bounded confidence
- отсутствие утверждения о подтвержденном exploit только на основании pattern evidence

## 5. Запустить repo-scale smart-contract case

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\protocols\SyntheticLendingProtocol\contracts\LendingPool.sol --pack lending_protocol_benchmark_pack "Benchmark the scoped lending protocol for collateral, liquidation, reserve, fee, and debt-accounting review lanes."
```

Смотреть:

- bounded contract inventory
- local import graph
- entrypoint review lanes
- collateral/liquidation и fee/reserve/debt-accounting lanes
- границы ручной проверки

## 6. Сверить ожидаемые формы отчета

Сравни вывод с:

- [EXPECTED_REPORT_SHAPES.ru.md](EXPECTED_REPORT_SHAPES.ru.md)
- [golden_manifest.json](golden_manifest.json)

Формулировки не обязаны совпадать дословно. Главное, чтобы сохранялась та же
позиция по доказательной базе: что реально наблюдалось локально, что является
только review priority, а что все еще требует экспертной проверки.
