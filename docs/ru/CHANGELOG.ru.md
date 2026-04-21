# Журнал изменений

Здесь кратко фиксируются заметные публичные изменения EllipticZero.

Проект сейчас идет по source-available release track под `FSL-1.1-ALv2`.
Текущая версия пакета: `0.1.1`.

## Не выпущено

### Добавлено

- `report_snapshot_summary` и `report_snapshot_count` в manifest и bundle
  overview, чтобы compact ECC / smart-contract triage и remediation-delta
  сигналы были видны без открытия полного session JSON.
- Режим `--evaluation-summary --replay-session/--replay-manifest/--replay-bundle`
  для короткой reviewer-сводки сохраненного запуска без повторного выполнения.
- Сводки сохраненных запусков теперь включают блок `review_status` с глубиной
  доказательной базы, comparison readiness, недостающими артефактами и
  manual-review posture.

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
- Короткие case-study snapshots для оценки ECC point-format review,
  vault-permission review и repo-scale lending-protocol triage.

## 0.1.0 - 2026-04-13

Первый публичный release track под FSL.

### Добавлено

- Локальный ограниченный исследовательский workflow для ECC и аудита
  смарт-контрактов.
- Оркестрируемые агентные роли: Orchestrator, Math, Cryptography, Strategy,
  Hypothesis, Critic и Report.
- Воспроизводимые session artifacts, traces, manifests, bundles, replay и
  doctor/self-check пути.
- ECC benchmark depth для point formats, curve metadata, aliases, curve-family
  transitions, subgroup/cofactor hygiene, twist hygiene и ограниченных
  domain-completeness проверок.
- Smart-contract repo-scale audit слой с parser, compile, inventory,
  first-party/dependency scoping, protocol maps, entrypoint lanes,
  function-family priorities, casebook matching, benchmark packs и before/after
  comparison support.
- Golden/synthetic evaluator cases для стабильных ECC и smart-contract
  smoke-проверок.
- Конфигурация провайдеров `mock`, `openai`, `openrouter`, `gemini` и
  `anthropic`, а также live smoke проверки, если пользователь передает свои
  ключи.
- Buyer-facing документация по лицензированию, коммерческому использованию,
  профилям окружения, сценариям применения, примерам отчетов и оценке проекта.
- GitHub issue templates, pull-request template, tests workflow, CodeQL
  workflow, Dependabot configuration и security policy.

### Безопасность и границы

- Ограниченные правила загрузки локальных plugins.
- Export-root filtering для reproducibility manifests и bundles.
- Формулировки отчетов, которые разделяют локальную доказательную базу,
  интерпретацию модели, confidence, residual risk и manual-review boundaries.
- Responsible-use и private vulnerability-reporting документация.

### Лицензирование

- Публичное source-available лицензирование под `FSL-1.1-ALv2`.
- Future-license transition к Apache License 2.0 для каждой опубликованной
  версии через два года после даты доступности этой версии.
- Отдельные commercial-license пояснения для competing commercial use, hosted
  или managed service, SaaS/platform deployment, OEM, white-label, resale и
  похожих продуктовых сценариев.
