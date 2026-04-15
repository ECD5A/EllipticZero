# Ожидаемые формы отчетов

Этот файл описывает, что должен сохранять полезный отчет EllipticZero при
запуске golden synthetic cases. Описание намеренно качественное: точные
формулировки и количество артефактов могут зависеть от локальных инструментов,
опциональных адаптеров и выбранного provider.

## `ecc-secp256k1-domain-completeness`

Что ожидается в полезном выводе:

- выбран пакет `ecc_domain_completeness_benchmark_pack`
- выполненные шаги пакета видны в сессии и отчете
- curve-domain metadata описана как локальное доказательство
- границы по generator/order/cofactor или family-completeness явно обозначены
- уверенность остается ограниченной и не превращается в заявление о криптографическом взломе

Хороший сигнал для оценки:

- по отчету понятно, что именно было проверено и что остается ручным review-вопросом

## `ecc-25519-subgroup-hygiene`

Что ожидается в полезном выводе:

- выбран пакет `ecc_subgroup_hygiene_benchmark_pack`
- видны subgroup, cofactor, twist или encoding lanes
- coordinate или family caveat отделены от production finding
- уверенность остается ограниченной
- границы ручной проверки сохранены

Хороший сигнал для оценки:

- отчет отделяет локальные review-сигналы от подтвержденных доказательств по конкретной implementation

## `ecc-secp256k1-point-format-edge`

Что ожидается в полезном выводе:

- выбран пакет `point_format_inspection_pack`
- видны point-format или prefix evidence
- bounded consistency output отделен от более сильных криптографических заявлений
- уверенность остается ограниченной
- отчет не заявляет private-key recovery или production library vulnerability

Хороший сигнал для оценки:

- отчет трактует malformed или edge-format evidence как review signal, а не как exploit

## `contract-vault-permission-lane`

Buyer-visible anchors для этого case:

- `Finding Cards` видны в верхней части отчета и сохраняют potential finding, evidence, why it matters, fix direction и recheck path
- `Evidence Coverage` и reproducibility outputs видны без погружения в raw JSON artifacts
- `Toolchain Fingerprint` и `Secret Redaction` остаются доступны в export-quality слое

Что ожидается в полезном выводе:

- выбран пакет `vault_permission_benchmark_pack`
- parser output включает синтетический vault-контракт и его externally reachable функции
- surface summary подсвечивает payable, value-flow, share/accounting, permission или signature-style lanes, если они есть в локальном разборе
- manual review queue и residual-risk строки остаются видны
- отчет не заявляет подтвержденный exploit только на основании pattern evidence

Хороший сигнал для оценки:

- отчет дает покупателю или ревьюеру понятный первый triage path без завышения результата

## `contract-governance-timelock-lane`

Что ожидается в полезном выводе:

- выбран пакет `governance_timelock_benchmark_pack`
- видны governance, timelock, emergency, upgrade-control, delegatecall или timestamp lanes, если локальный разбор их поддерживает
- execution и upgrade surfaces описаны как ограниченные review priorities
- manual review queue и exit criteria остаются видны
- отчет не заявляет полную безопасность upgrade-логики или подтвержденный takeover path

Хороший сигнал для оценки:

- отчет показывает, куда человеку-ревьюеру смотреть дальше и какие локальные сигналы это обосновали

## `contract-repo-scale-lending-protocol`

Что ожидается в полезном выводе:

- выбран пакет `lending_protocol_benchmark_pack`
- bounded contract inventory показывает файлы scoped protocol
- local import graph связывает `LendingPool.sol`, `OracleAdapter.sol` и `ReserveVault.sol`
- entrypoint review lanes включают collateral, liquidation, reserve, fee или debt-accounting signals
- manual review queue и bounded confidence остаются видны
- отчет не заявляет complete protocol audit или confirmed insolvency exploit

Хороший сигнал для оценки:

- отчет демонстрирует repo-scale triage: должно быть понятно, какие файлы и lanes человеку проверять первыми
