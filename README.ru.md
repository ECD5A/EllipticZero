# EllipticZero

EllipticZero — локальная лаборатория с доступным исходным кодом по модели source-available для ограниченных защитных исследований в двух доменах:

- ECC / защитная криптография
- аудит смарт-контрактов

Пользовательский цикл остаётся простым: выбрать язык, выбрать домен, при необходимости выбрать кривую или передать код контракта, ввести исследовательскую идею, запустить ограниченную локальную сессию и посмотреть собранную доказательную базу с итоговым отчётом.

## Скриншоты

![Стартовый экран EllipticZero](docs/assets/console-home-ru.png)

![Экран итогового отчёта EllipticZero](docs/assets/session-report-ru.png)

## Что Есть В Проекте

- исследовательские сессии с оркестратором в центре цикла
- агенты Math, Cryptography, Strategy, Hypothesis, Critic и Report
- локальные изолированные раннеры для символьных, формальных, проверок свойств, фаззинга и ECC testbed-проверок
- встроенные ECC benchmark-наборы для point anomalies, encoding edges, curve aliases, curve-family transitions, subgroup/cofactor и twist hygiene, а также bounded domain completeness
- инструменты аудита смарт-контрактов: разбор кода, компиляция, инвентаризация репозитория контрактов, ограниченный анализ импортов и зависимостей, карта протокольных модулей, маршруты обзора, приоритизация семейств функций и сведение межфайловых сигналов в общие приоритеты
- встроенные проверочные корпуса для asset-flow, vault/share, oracle freshness, collateral/liquidation и liquidation-fee review, protocol-fee/reserve-buffer/debt accounting, bad-debt socialization и смежных protocol-style семейств обзора
- ограниченные repo-casebook сценарии для upgrade/storage, governance/timelock, asset-flow, oracle/liquidation, protocol accounting, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery и vault/permit, а также опциональные адаптеры `Slither`, `Foundry` и `Echidna`, если они установлены локально
- встроенные smart-contract benchmark-пакеты для static baseline review, repo-casebook benchmarking, protocol-style repo benchmarking, а также для governance/timelock, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery, vault/permission и lending-style проходов
- трассировки, манифесты, пакеты воспроизводимости, повторный запуск и `doctor`
- `mock` по умолчанию, а также `openai`, `openrouter`, `gemini` и `anthropic` при корректной настройке

## Быстрый Старт

Требования:

- Python 3.11+
- доступ к локальной файловой системе для артефактов
- API-ключ нужен только если требуется выйти за пределы `mock`

Установка:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[lab]
```

Или используй:

```powershell
.\scripts\setup_local_lab.ps1
```

Локальная установка с упором на аудит смарт-контрактов:

```powershell
.\scripts\setup_local_lab.ps1 -Profile smart-contract-static
```

Запуск интерфейса:

```powershell
python -m app.main --interactive
```

Проверка готовности системы:

```powershell
python -m app.main --doctor
```

В интерактивной консоли язык можно переключать без перезапуска клавишами `F2` или `L`.

## Полезные Команды

Прямая исследовательская сессия:

```powershell
python -m app.main "Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output."
```

Ограниченный исследовательский режим:

```powershell
python -m app.main "Explore whether ECC point parsing and on-curve checks reveal bounded defensive research leads." --research-mode sandboxed_exploratory
```

Аудит смарт-контракта из локального файла:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for low-level call review surfaces and externally reachable value flow."
```

Аудит смарт-контракта из встроенного кода:

```powershell
python -m app.main --domain smart_contract_audit --contract-code "pragma solidity ^0.8.20; contract Vault {}" "Review the contract for reachable admin, upgrade, and external-call surfaces."
```

Benchmark-пакет для смарт-контракта из локального файла:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

Просмотр маршрутизации:

```powershell
python -m app.main --show-routing
```

Дополнительные CLI-утилиты:

```powershell
python -m app.main --list-synthetic-targets
python -m app.main --list-packs
python -m app.main --live-provider-smoke openai --live-smoke-model gpt-4.1-mini
python -m app.main --live-provider-smoke openrouter --live-smoke-model <openrouter-model-id>
python -m app.main --replay-session .\artifacts\sessions\session_id.json
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Повторно прогнать bounded-аудит и записать различия до/после относительно сохранённой baseline-сессии."
```

## Конфигурация И Runtime

- Конфигурация читается из базовых значений, `configs/settings.yaml`, переменных окружения и необязательного `.env`.
- Поддерживаемые провайдеры: `mock`, `openai`, `openrouter`, `gemini`, `anthropic`.
- Нормальный сценарий — один общий провайдер и одна модель для всех ролей. Переопределения по ролям доступны как продвинутый вариант настройки.
- OpenRouter может быть удобным bounded smoke-путём для live-проверки, потому что даёт OpenAI-compatible API и единый ключ для многих моделей. Если использовать варианты с суффиксом `:free`, относись к ним как к удобной проверке, а не как к гарантированному runtime: у OpenRouter есть свои лимиты по частоте и дневному объёму таких запросов.
- Локальная среда может включать `SymPy`, `Hypothesis`, `z3-solver`, встроенные мутационные пробы, ECC-тестбеды, проверки для аудита смарт-контрактов и `SageMath`, если он доступен.
- ECC-отчёт теперь может включать краткую benchmark-сводку, benchmark-статус, покрытие ECC-семейств, короткие сводки по benchmark-кейсам, bounded ECC review focus, строки с остаточным риском, заметки по согласованности ECC-сигналов, короткую ECC validation matrix, осторожные строки ECC-сравнения до/после, заметки по ECC benchmark-delta и ECC-регрессионные дельты, когда локальные сигналы по encoding, family transitions, twist hygiene, subgroup/cofactor или domain completeness это оправдывают.
- Setup-профили могут развернуть управляемый Solidity-компилятор в `.ellipticzero/tooling/solcx`, чтобы проверки компиляции и зависящие от компилятора адаптеры не зависели от глобальной установки `solc`.
- Анализ Solidity работает с учётом версии: сначала читается `pragma` контракта, а затем система выбирает совместимый локально доступный управляемый компилятор вместо привязки к одной фиксированной версии `solc`.
- Для аудита смарт-контрактов можно использовать вставку кода, встроенный код в CLI или локальный файл `.sol` / `.vy`.
- `doctor` теперь отдельно показывает конфигурацию провайдера и готовность hosted live-smoke path, а прямой smoke-run выводит фактический тайм-аут и лимит токенов запроса.
- `doctor` теперь также показывает bounded local plugin safety gate и политику approved export roots, используемую при экспорте manifest и bundle.
- Сессия по смарт-контракту может нести локальный корень контрактного репозитория, чтобы ограниченный аудит строил инвентаризацию репозитория, маршруты обзора по entrypoint-файлам, приоритеты семейств функций, сводки по маршрутам семейств рисков, подсказки по общим зависимостям и сравнение с ограниченными repo-casebook сценариями. Если используется локальный файл контракта, интерактивный flow теперь автоматически выводит ограниченный локальный корень.
- Smart-contract experiment packs теперь могут структурировать bounded static benchmarking, repo-casebook benchmarking, protocol-style benchmark passes, а также более узкие governance/timelock, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery, vault/permission и lending-style benchmark passes; их выполненные шаги сохраняются в сессии, replay-артефактах и итоговом отчёте.
- Прямые CLI-аргументы `--compare-session`, `--compare-manifest` и `--compare-bundle` теперь позволяют привязать сохранённую baseline-сессию к новому bounded-запуску, чтобы итоговый отчёт мог показать осторожные различия до/после и флаги возможных регрессий.
- Отчёт по смарт-контракту может включать инвентаризацию контрактов, карту протокольных модулей, инварианты протокола, сводку по согласованности сигналов, матрицу валидации, benchmark-статус, сильнейшие приоритеты по обзору репозитория, триаж первого ограниченного прохода, маршруты обзора по entrypoint-файлам, приоритеты семейств функций и сводки по семействам рисков.
- Отчёт по смарт-контракту также может включать сводку по ограниченному покрытию repo-casebook, компактные сводки по совпавшим сценариям, archetype-style подписи для governance/timelock, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery и похожих protocol-style case-study линий, короткие строки с ключевыми совпавшими кейсами, короткий блок с оставшимися пробелами, benchmark-сводки, casebook-triage и блок связки инструментов для сильнейших маршрутов обзора по репозиторию.
- Отчёт по смарт-контракту также может включать сводки по benchmark-пакетам и короткие benchmark-case summary, если bounded contract benchmark pack материально влиял на сессию.
- Отчёт по смарт-контракту также может включать матрицу покрытия casebook, benchmark-статус и более жёсткий validation posture для сильнейших маршрутов обзора по репозиторию, включая bounded repo-casebook-сценарии, которые поддерживают сразу несколько семейств рисков в одном проходе.
- Когда локальные сигналы это оправдывают, отчёт по смарт-контракту может также включать короткую очередь проверки, строки с остаточным риском для сильнейших маршрутов обзора, критерии завершения для сильнейшего маршрута обзора, статус компиляции, сводку по поверхности контракта, встроенные результаты проверок риск-паттернов, протокольный фокус, заметки по ограниченной проверке защитной доработки, приоритеты повторной проверки после доработки, осторожные рекомендации по защитной доработке, внешние результаты статического анализа и сравнение с ограниченными проверочными корпусами или repo-casebook-сценариями, где replay-путь может идти сразу по нескольким совпавшим семействам, если маршрут обзора действительно их объединяет, а также строки сравнения до/после и флаги возможных регрессий, когда к запуску привязана сохранённая baseline-сессия.
- Завершённые запуски могут сохранять файл сессии, трассировку, сравнительный отчёт и пакет воспроизводимости в `artifacts/`, а пакет воспроизводимости теперь включает `overview.json` со сводкой фокуса, готовностью к сравнению, экспортными счётчиками и сводками по quality gates / hardening.
- Кросс-доменный отчёт теперь тоже может сохранять quality gates и hardening summary, чтобы глубина доказательной базы, готовность к сравнению, export posture и остаточные manual-review lanes были видны в одном месте.
- Manifest и bundle теперь фильтруют ссылки на артефакты, которые разрешаются вне approved local storage roots, а unsafe local plugin path layouts блокируются ещё до загрузки в реестр.

Локальные настройки смотри в `.env.example`.

## Документация Проекта

- [ARCHITECTURE.ru.md](docs/ru/ARCHITECTURE.ru.md)
- [AGENTS.ru.md](docs/ru/AGENTS.ru.md)
- [LICENSE_TRANSITION.ru.md](docs/ru/LICENSE_TRANSITION.ru.md)
- [COMMERCIAL_LICENSE.ru.md](docs/ru/COMMERCIAL_LICENSE.ru.md)
- [TRADEMARKS.ru.md](docs/ru/TRADEMARKS.ru.md)
- [REPRODUCIBILITY.ru.md](docs/ru/REPRODUCIBILITY.ru.md)
- [REPORT_SPEC.ru.md](docs/ru/REPORT_SPEC.ru.md)
- [SECURITY.ru.md](docs/ru/SECURITY.ru.md)
- [CONTRIBUTING.ru.md](docs/ru/CONTRIBUTING.ru.md)

## Проверка

```powershell
python -m pip check
python -m ruff check .
python -m compileall app tests scripts
pytest -q
```

Сейчас проект проходит тесты в `mock`-режиме.

## Поддержка Проекта

- Bitcoin (BTC): `1ECDSA1b4d5TcZHtqNpcxmY8pBH1GgHntN`
- USDT (TRC20): `TSWcFVfqCp4WCXrUkkzdCkcLnhtFLNN3Ba`

## Ответственное Использование

Используй EllipticZero только для авторизованного локального исследования. Держи эксперименты ограниченными, обратимыми и проверяемыми.

## Лицензия

Этот репозиторий распространяется по лицензии **FSL-1.1-ALv2**.

Публичная версия доступна с исходным кодом для оценки, исследований,
внутреннего использования и иных разрешённых целей по условиям лицензии.

Каждая опубликованная версия становится доступной по Apache License 2.0 через
два года после даты её публикации.

Если вам нужны права сверх публичной лицензии, включая конкурирующее
коммерческое использование, hosted or managed service, OEM, white-label или
перепродажу, смотрите [COMMERCIAL_LICENSE.ru.md](docs/ru/COMMERCIAL_LICENSE.ru.md).

Права на бренд и название не передаются вместе с лицензией на код. См.
[TRADEMARKS.ru.md](docs/ru/TRADEMARKS.ru.md).

## Коммерческое Использование

Если ваш сценарий включает конкурирующий коммерческий продукт, коммерческий
hosted-сервис, OEM-дистрибуцию, white-label использование или перепродажу,
нужно получать отдельную коммерческую лицензию.

См. [COMMERCIAL_LICENSE.ru.md](docs/ru/COMMERCIAL_LICENSE.ru.md).

## Контакты

По вопросам коммерческой лицензии, сотрудничества и партнёрств:

- Email: `stelmak159@gmail.com`
- Telegram: `@ECDS4`
- Репозиторий: `https://github.com/ECD5A/EllipticZero`
