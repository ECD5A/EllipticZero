# Golden synthetic cases

В этой папке лежат безопасные синтетические кейсы для оценки EllipticZero без
приватного клиентского репозитория и без live API-ключей.

Цель этих кейсов не в том, чтобы доказать обнаружение каждой проблемы. Цель -
сделать понятным сам рабочий цикл:

- выбрать ограниченный кейс
- запустить подходящий benchmark-пакет
- посмотреть выполненные шаги пакета и локальные доказательства
- проверить, что итоговый отчет сохраняет границы уверенности и ручные review lanes

## Состав

- [golden_manifest.json](golden_manifest.json) описывает поддерживаемые кейсы, ожидаемые пакеты и форму отчета.
- [RUNBOOK.ru.md](RUNBOOK.ru.md) дает короткий evaluator path по golden cases.
- [EXPECTED_REPORT_SHAPES.ru.md](EXPECTED_REPORT_SHAPES.ru.md) объясняет, что должен содержать полезный отчет по каждому кейсу.
- [contracts/SyntheticVault.sol](contracts/SyntheticVault.sol) - безопасный fixture для vault/permission review.
- [contracts/SyntheticGovernanceTimelock.sol](contracts/SyntheticGovernanceTimelock.sol) - безопасный fixture для governance/timelock и upgrade-control review.
- [protocols/SyntheticLendingProtocol](protocols/SyntheticLendingProtocol) - безопасный repo-scale fixture для lending protocol review.
- [ecc/secp256k1_metadata_seed.txt](ecc/secp256k1_metadata_seed.txt) - seed для ECC domain-completeness проверки.
- [ecc/curve25519_subgroup_seed.txt](ecc/curve25519_subgroup_seed.txt) - seed для subgroup/cofactor hygiene проверки.
- [ecc/secp256k1_point_format_edge_seed.txt](ecc/secp256k1_point_format_edge_seed.txt) - seed для ECC point-format edge проверки.

## Быстрые запуски

ECC domain completeness:

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether secp256k1 curve-domain assumptions are complete enough for cautious defensive reporting."
```

ECC subgroup hygiene:

```powershell
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, twist, and encoding assumptions for 25519-family defensive analysis."
```

ECC point-format edge:

```powershell
python -m app.main --pack point_format_inspection_pack "Inspect a compressed secp256k1 public-key encoding edge and keep format evidence separate from stronger cryptographic claims."
```

Vault/permission lane для смарт-контракта:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticVault.sol --pack vault_permission_benchmark_pack "Benchmark vault share-accounting, permission, and externally reachable value-flow review lanes."
```

Governance/timelock lane для смарт-контракта:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\contracts\SyntheticGovernanceTimelock.sol --pack governance_timelock_benchmark_pack "Benchmark governance timelock, upgrade-control, and emergency-lane review surfaces."
```

Repo-scale lending protocol lane:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\examples\golden_cases\protocols\SyntheticLendingProtocol\contracts\LendingPool.sol --pack lending_protocol_benchmark_pack "Benchmark the scoped lending protocol for collateral, liquidation, reserve, fee, and debt-accounting review lanes."
```

## Как оценивать

Кейсы специально сделаны синтетическими. Они проверяют parser, surface,
benchmark, report и confidence-calibration пути, но не публикуют реальные
эксплуатационные материалы.

Хороший вывод должен сохранять то, что реально наблюдалось локально. Он не
должен превращать review lane в подтвержденную уязвимость без дополнительной
локальной доказательной базы.
