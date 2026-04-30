# Журнал изменений

Здесь кратко фиксируются заметные публичные изменения EllipticZero.

Проект идёт по source-available release track под `FSL-1.1-ALv2`.
Версия пакета: `0.1.7`.

## 0.1.7 - 2026-04-30

### Добавлено

- Нормализованные smart-contract находки для встроенных pattern checks: каждая
  кандидатная находка хранит severity, confidence, локальную evidence,
  подсказку по строке, направление исправления и путь повторной проверки в
  `result_data`.
- Сигналы проверки deadline / expiry для permit-like signature путей, где
  используется `ecrecover` без явной границы срока действия.
- Сигналы Chainlink-style oracle round completeness для `latestRoundData` /
  `getRoundData`, если путь не сохраняет проверку вида
  `answeredInRound >= roundId`.

### Изменено

- Формулировки smart-contract слоя сдвинуты от слишком широкого audit wording к
  scoped security review и нормализованным review-сигналам.

## 0.1.6 - 2026-04-30

### Добавлено

- Интерактивный smart-contract ввод принимает папку контрактов:
  консоль выбирает представительный Solidity/Vyper файл и сохраняет scoped
  contract root для repo-scale review.
- Добавлен `contract-reentrancy-review-lane` - безопасный синтетический golden
  case для external-call ordering, withdrawal accounting и reentrancy-adjacent
  review lanes.
- Добавлены подсказки по строкам для встроенных smart-contract сигналов,
  карточек находок, пунктов ручной проверки и SARIF-экспорта.

### Изменено

- Публичное позиционирование переставлено на smart-contract audit первым, а
  defensive ECC research оставлен вторым поддерживаемым доменом.
- README и документы оценки ужаты: меньше повторяющихся списков, короче
  описания для ревьюеров.

## 0.1.5 - 2026-04-29

### Добавлено

- Добавлен лёгкий слой известных кейсов: метаданные из
  разрешённых источников SmartBugs и семейств детекторов Slither можно
  кэшировать локально, сопоставлять с сигналами аудита смарт-контрактов и
  показывать в отчётах без запуска удалённого кода.
- В интерактивную лабораторию оценки добавлен пункт `ИЗВЕСТНЫЕ КЕЙСЫ` для
  обновления профилей, просмотра локального кэша и проверки разрешённых
  источников метаданных.
- Усилен smart-contract review в заданных рамках: добавлены сигналы по domain separation
  для подписей, границам Chainlink-style oracle answer и немедленным upgrade
  путям без явной задержки, очереди или governance-контроля.
- Добавлены review-сигналы для token balance-delta и oracle decimal scaling,
  чтобы лучше подсвечивать fee-on-transfer accounting и price-precision проверки.
- Добавлены соответствующие встроенные corpus-кейсы для token balance-delta и
  oracle decimal scaling, чтобы новые семейства покрывались локальными benchmark
  sweeps.
- Усилен приём evidence от Slither и Foundry: находки Slither сохраняют
  нормализованные severity и source-location summaries, а Foundry-проекты могут
  добавлять локальные `forge test` результаты при наличии `foundry.toml`.

### Изменено

- `ЛАБОРАТОРИЯ ОЦЕНКИ` вынесена в главное интерактивное меню, а прежний
  расширенный раздел переименован в `СИСТЕМА / ИНСТРУМЕНТЫ`, чтобы уменьшить
  вложенность навигации.

## 0.1.4 - 2026-04-28

### Добавлено

- Добавлен экспорт Markdown-отчёта сохранённого запуска через
  `--export-report-md`.
- Добавлена короткая сводка проверки в верхней части консольного и
  Markdown-отчёта.
- Улучшено первое знакомство в mock-режиме: локализованы ошибки валидации,
  вход больше не режется по списку знакомых терминов, добавлены компактные
  примеры ввода, а итог в консоли выводится отдельным блоком.
- Добавлено меню действий после завершения сессии, включая выгрузку
  `report.md` и `review.sarif` в один шаг.
- Добавлен интерактивный раздел `ЛАБОРАТОРИЯ ОЦЕНКИ` для golden cases,
  experiment packs, сводок проекта или сохранённого запуска, baseline-сравнения
  и предварительного просмотра контекста провайдера.
- Пакеты воспроизводимости включают `report.md`, если в сессии есть отчёт.
  JSON-артефакты остаются основой доказательной базы.

## 0.1.3 - 2026-04-26

### Добавлено

- Итоговый CLI-отчёт показывает готовую команду для оценки сохранённого
  запуска, если для него создан пакет воспроизводимости.
- Добавлен экспорт сохранённых запусков в SARIF 2.1.0 для CI и GitHub Code
  Scanning.
- SARIF-результаты содержат стабильные partial fingerprints, теги и уровень
  серьёзности EllipticZero для более аккуратного CI-триажа.
- Добавлена CLI-команда `--provider-context-preview`, чтобы до live-вызова
  модели увидеть, какой контекст может уйти hosted-провайдеру.
- Руководства по оценке и безопасности расширены блоками про приватность
  провайдеров, границы sandbox, границы артефактов, golden cases и SARIF.

## 0.1.2 - 2026-04-21

### Добавлено

- `report_snapshot_summary` и `report_snapshot_count` в manifest и bundle
  overview, чтобы compact smart-contract / ECC triage и remediation-delta
  сигналы были видны без открытия полного session JSON.
- Режим `--evaluation-summary --replay-session/--replay-manifest/--replay-bundle`
  для короткой сводки сохранённого запуска без повторного выполнения.
- Сводки сохранённых запусков включают блок `review_status` с глубиной
  доказательной базы, готовностью к сравнению, недостающими артефактами и
  статусом ручной проверки.

## 0.1.1 - 2026-04-15

### Добавлено

- JSON-вывод `--evaluation-summary --evaluation-summary-format json` для
  автоматической оценки и интеграционных сценариев.
- Карточки smart-contract находок, связывающие bounded потенциальные issues с
  доказательной базой, контекстом риска, направлением защитной доработки и
  путём повторной проверки.
- Сводки evidence coverage, toolchain fingerprints и secret-redaction summaries
  в отчётах, manifest, bundle overview и export notes.
- Редактирование вероятных секретов в saved session JSON, trace JSONL,
  comparative-report и bundle JSON snapshots перед экспортом.
- Demo path для no-key vault/permission golden case.
- Более компактный текст smart-contract finding cards для первого экрана отчёта.
- Компактная CLI-команда `--evaluation-summary` для быстрой оценки проекта без
  API-ключей.
- Короткие case-study snapshots для оценки vault-permission review,
  repo-scale lending-protocol triage и ECC point-format review.

## 0.1.0 - 2026-04-13

Первый публичный release track под FSL.

### Добавлено

- Локальный ограниченный исследовательский workflow для аудита
  смарт-контрактов и ECC-исследований.
- Оркестрируемые агентные роли: Orchestrator, Math, Cryptography, Strategy,
  Hypothesis, Critic и Report.
- Воспроизводимые session artifacts, traces, manifests, bundles, replay и
  doctor/self-check пути.
- Smart-contract repo-scale audit слой с parser, compile, inventory,
  first-party/dependency scoping, protocol maps, entrypoint lanes,
  function-family priorities, casebook matching, benchmark packs и before/after
  comparison support.
- ECC benchmark depth для point formats, curve metadata, aliases, curve-family
  transitions, subgroup/cofactor hygiene, twist hygiene и ограниченных
  domain-completeness проверок.
- Golden/synthetic evaluator cases для стабильных smart-contract и ECC
  smoke-проверок.
- Конфигурация провайдеров `mock`, `openai`, `openrouter`, `gemini` и
  `anthropic`, а также live smoke проверки, если пользователь передаёт свои
  ключи.
- Buyer-facing документация по лицензированию, коммерческому использованию,
  профилям окружения, сценариям применения, примерам отчётов и оценке проекта.
- GitHub issue templates, pull-request template, tests workflow, CodeQL
  workflow, Dependabot configuration и security policy.

### Безопасность и границы

- Ограниченные правила загрузки локальных plugins.
- Export-root filtering для reproducibility manifests и bundles.
- Формулировки отчётов, которые разделяют локальную доказательную базу,
  интерпретацию модели, confidence, residual risk и manual-review boundaries.
- Responsible-use и private vulnerability-reporting документация.

### Лицензирование

- Публичное source-available лицензирование под `FSL-1.1-ALv2`.
- Future-license transition к Apache License 2.0 для каждой опубликованной
  версии через два года после даты доступности этой версии.
- Отдельные commercial-license пояснения для competing commercial use, hosted
  или managed service, SaaS/platform deployment, OEM, white-label, resale и
  похожих продуктовых сценариев.
