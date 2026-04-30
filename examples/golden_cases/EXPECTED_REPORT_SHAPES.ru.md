# Ожидаемые формы отчётов

Этот файл описывает, что должен сохранять полезный отчёт EllipticZero при
запуске golden synthetic cases. Описание намеренно качественное: точные
формулировки и количество артефактов могут зависеть от локальных инструментов,
опциональных адаптеров и выбранного провайдера.

## `contract-vault-permission-lane`

Что должно быть видно оценщику в этом кейсе:

- `Finding Cards` видны в верхней части отчёта и сохраняют potential finding, evidence, why it matters, fix direction и recheck path
- `Evidence Coverage` и артефакты воспроизводимости видны без погружения в raw JSON artifacts
- `Toolchain Fingerprint` и `Secret Redaction` остаются доступны в export-quality слое

Что ожидается в полезном выводе:

- выбран пакет `vault_permission_benchmark_pack`
- parser output включает синтетический vault-контракт и его externally reachable функции
- surface summary подсвечивает payable, value-flow, share/accounting, permission или signature-style lanes, если они есть в локальном разборе
- manual review queue и строки с остаточным риском остаются видны
- отчёт не заявляет подтверждённый exploit только на основании pattern evidence

Хороший сигнал для оценки:

- отчёт даёт покупателю или ревьюеру понятный первый путь первичного разбора без завышения результата

## `contract-reentrancy-review-lane`

Что ожидается в полезном выводе:

- выбран пакет `contract_static_benchmark_pack`
- parser output включает синтетический reentrancy-style vault и его externally reachable функции
- surface или pattern summary подсвечивает external-call ordering, value-flow, withdrawal accounting или reentrancy-adjacent lanes, если они есть в локальном разборе
- manual review queue и bounded confidence остаются видны
- отчёт не заявляет подтверждённый exploit только на основании pattern evidence

Хороший сигнал для оценки:

- отчёт показывает конкретную линию проверки и путь перепроверки, не превращая синтетическую фикстуру в эксплуатационную инструкцию

## `contract-governance-timelock-lane`

Что ожидается в полезном выводе:

- выбран пакет `governance_timelock_benchmark_pack`
- видны governance, timelock, emergency, upgrade-control, delegatecall или timestamp lanes, если локальный разбор их поддерживает
- execution и upgrade surfaces описаны как ограниченные review priorities
- manual review queue и exit criteria остаются видны
- отчёт не заявляет полную безопасность upgrade-логики или подтверждённый takeover path

Хороший сигнал для оценки:

- отчёт показывает, куда человеку-ревьюеру смотреть дальше и какие локальные сигналы это обосновали

## `contract-repo-scale-lending-protocol`

Что ожидается в полезном выводе:

- выбран пакет `lending_protocol_benchmark_pack`
- bounded contract inventory показывает файлы scoped protocol
- local import graph связывает `LendingPool.sol`, `OracleAdapter.sol` и `ReserveVault.sol`
- entrypoint review lanes включают collateral, liquidation, reserve, fee или debt-accounting signals
- manual review queue и bounded confidence остаются видны
- отчёт не заявляет complete protocol audit или confirmed insolvency exploit

Хороший сигнал для оценки:

- отчёт демонстрирует repo-scale triage: должно быть понятно, какие файлы и линии проверки человеку проверять первыми

## `ecc-secp256k1-domain-completeness`

Что ожидается в полезном выводе:

- выбран пакет `ecc_domain_completeness_benchmark_pack`
- выполненные шаги пакета видны в сессии и отчёте
- curve-domain metadata описана как локальное доказательство
- границы по generator/order/cofactor или family-completeness явно обозначены
- уверенность остаётся ограниченной и не превращается в заявление о криптографическом взломе

Хороший сигнал для оценки:

- по отчёту понятно, что именно было проверено и что остаётся вопросом для ручной проверки

## `ecc-25519-subgroup-hygiene`

Что ожидается в полезном выводе:

- выбран пакет `ecc_subgroup_hygiene_benchmark_pack`
- видны линии проверки по subgroup, cofactor, twist или encoding
- оговорки по координатам или семейству отделены от более сильного вывода
- уверенность остаётся ограниченной
- границы ручной проверки сохранены

Хороший сигнал для оценки:

- отчёт отделяет локальные сигналы для проверки от подтверждённых доказательств по конкретной реализации

## `ecc-secp256k1-point-format-edge`

Что ожидается в полезном выводе:

- выбран пакет `point_format_inspection_pack`
- видны сигналы по point-format или prefix
- bounded consistency output отделён от более сильных криптографических заявлений
- уверенность остаётся ограниченной
- отчёт не заявляет восстановление закрытого ключа или уязвимость production-библиотеки

Хороший сигнал для оценки:

- отчёт трактует malformed или edge-format evidence как сигнал для проверки, а не как exploit
