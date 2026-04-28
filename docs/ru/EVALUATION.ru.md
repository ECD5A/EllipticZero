# Оценка EllipticZero

Этот документ помогает исследователям, командам безопасности, интеграторам и
потенциальным коммерческим партнёрам понять, как оценивать EllipticZero без
догадок и лишней возни.

EllipticZero рассчитан на прямую проверку: исходный код, документация, CLI,
локальные артефакты, отчёты, benchmark-пакеты и golden cases должны складываться
в одну понятную картину.

## Что можно оценивать

По условиям публичной лицензии `FSL-1.1-ALv2` репозиторий можно читать,
собирать, запускать локально и оценивать для исследований, внутренней проверки
и других разрешенных целей.

Полезные пути оценки:

- просмотр кода оркестрации, агентных ролей, раннеров, отчётов и границ экспорта
- локальная CLI-проверка без ключей в `mock`-режиме
- golden/synthetic cases для стабильных smoke-проверок
- ECC benchmark-пакеты по point format, curve metadata, subgroup, cofactor,
  twist и domain-completeness поверхностям
- smart-contract audit по parser, compile, repo inventory, casebook, benchmark,
  comparison и manual-review lanes
- проверка с реальными провайдерами на ваших собственных API-ключах
- просмотр session, trace, manifest, bundle и replay-артефактов
- экспорт сохранённых запусков в SARIF для CI или GitHub Code Scanning

`mock`-режим - это самый простой старт без ключей, но не единственный способ
оценки проекта.

## Быстрый путь без ключей

Установить lab-профиль:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[lab]
```

Проверить локальную среду:

```powershell
python -m app.main --doctor
```

Вывести компактную сводку для оценки проекта:

```powershell
python -m app.main --evaluation-summary
```

Сводка в JSON для автоматической проверки:

```powershell
python -m app.main --evaluation-summary --evaluation-summary-format json
```

Для сохранённого запуска можно получить короткую сводку для проверки без повторного
выполнения:

```powershell
python -m app.main --evaluation-summary --replay-bundle .\artifacts\bundles\session_id
```

Сводка сохранённого запуска включает короткий блок `review_status`: глубину
доказательной базы, готовность к сравнению, недостающие артефакты для проверки
и статус ручного review.

Экспортировать пункты проверки сохранённого запуска в SARIF:

```powershell
python -m app.main --replay-bundle .\artifacts\bundles\session_id --export-sarif .\artifacts\sarif\session_id.sarif
```

SARIF-вывод рассчитан на CI и Code Scanning. В нем сохраняется
`reviewRequired=true`, потому что ограниченные сигналы всё еще требуют
локальной доказательной базы и ручной проверки до подтвержденных находок.

Экспортировать Markdown-отчёт сохранённого запуска:

```powershell
python -m app.main --replay-bundle .\artifacts\bundles\session_id --export-report-md .\artifacts\reports\session_id.md
```

Markdown-отчёт нужен для проверки, обмена и архива. Он намеренно не вставляет
полный seed или исходный код контракта; доказательной базой остаются session,
trace, manifest, bundle и локальные outputs инструментов. Верхняя сводка
показывает главный сигнал, следующий шаг проверки, состояние доказательной
базы и остаточный риск, если эти поля есть в сохранённом запуске.

Для menu-first сценария запусти интерактивную консоль и после завершения
сессии выбери `ВЫГРУЗИТЬ ФАЙЛЫ ПРОВЕРКИ`. Этот пункт создаёт `report.md` и
`review.sarif` внутри пакета сессии без ручного ввода export-флагов.

В той же интерактивной консоли есть раздел `ЛАБОРАТОРИЯ ОЦЕНКИ` для проверки
без API-ключей: golden cases, experiment packs, сводка проекта или сохранённого
запуска, baseline-сравнение и предварительный просмотр контекста провайдера.

Предварительно посмотреть контекст для hosted-провайдера перед live-запуском агентов:

```powershell
python -m app.main --provider openrouter --provider-context-preview "Проверить, какой контекст может уйти hosted-провайдеру."
```

Для проверки приватного контракта запускай предварительный просмотр с теми же
`--domain`, `--contract-file`, `--contract-root`, `--pack` и параметрами
провайдера, которые планируешь использовать. Провайдер при этом не вызывается.

Посмотреть встроенные golden cases:

```powershell
python -m app.main --list-golden-cases
```

Запустить ECC golden case:

```powershell
python -m app.main --golden-case ecc-secp256k1-point-format-edge
```

Запустить repo-scale golden case по смарт-контрактам:

```powershell
python -m app.main --golden-case contract-repo-scale-lending-protocol
```

## Демо-путь для продуктовой оценки

Для самой быстрой продуктовой оценки запусти vault/permission golden case:

```powershell
python -m app.main --golden-case contract-vault-permission-lane
```

На первом экране отчёта стоит проверить:

- `Finding Cards` с потенциальной находкой, доказательством, причиной важности, направлением исправления и путём перепроверки
- `Сводка триажа репозитория`, `Сводка ECC-триажа` или `Сводка изменений после доработки`, если входные данные оправдывают такой первый экран
- `Evidence Coverage` с количеством доказательств, числом tool-backed сигналов, использованными инструментами, типами экспериментов и пунктами проверки
- артефакты воспроизводимости для session, trace, comparative report и bundle
- `Toolchain Fingerprint` и `Secret Redaction` ниже, в export-quality слое

Этот путь специально работает без API-ключей и на synthetic case. Он показывает
форму рабочего цикла, которую коммерческий оценщик должен ожидать перед проверкой
частного репозитория.

## Benchmark scorecard

Benchmark-слой стоит воспринимать как проверочный список для оценки, а не как
обещание, что инструмент сам полностью проаудировал цель.

| Зона | Что проверять | Более сильный сигнал |
| --- | --- | --- |
| Golden cases | Встроенные ECC- и smart-contract кейсы запускаются чисто и дают ожидаемую форму отчёта. | Smoke-вывод стабилен при повторных локальных запусках. |
| ECC coverage | В отчёте видны форматы точек, метаданные кривых, subgroup/cofactor проверки, twist hygiene, переходы между семействами кривых, domain-completeness поверхности и компактная сводка ECC-триажа. | Локальные вычисления и интерпретация отчёта согласованы без завышения уверенности. |
| Smart-contract coverage | Parser, compile, inventory, repo map, casebook, benchmark pack, review queue, residual-risk lanes и компактная сводка триажа появляются, когда входные данные это оправдывают. | Отчёт отделяет подтверждённые локальные сигналы от приоритетов ручной проверки. |
| Comparison | Сохранённую baseline можно подключить через `--compare-session`, `--compare-manifest` или `--compare-bundle`. | Before/after строки и remediation-delta summary показывают осторожные изменения, возможные regression flags и следующий replay-path. |
| Export quality | Session, trace, manifest, bundle и `report.md` остаются внутри разрешённых локальных export roots. | Проверяющий может воспроизвести запуск, посмотреть evidence trail и передать Markdown-отчёт. |
| CI-проверка | Сохранённые запуски можно экспортировать в SARIF 2.1.0. | Code Scanning может показать ограниченные сигналы без автоматического превращения их в доказанные находки. |
| Приватность провайдера | `--provider-context-preview` запускается перед live-запуском hosted-агентов. | Проверяющий видит, может ли код контракта или путь к source-файлу уйти в hosted-маршруты. |
| Hosted path | Опциональный live smoke работает только когда проверяющий передаёт валидные credentials провайдера. | Ответ провайдера воспринимается как интерпретация, а не как доказательство. |

Пропуски в scorecard тоже полезны. Если какая-то линия проверки отсутствует, стоит
проверить: входные данные не оправдывали этот путь, локальный toolchain не был
установлен, prompt был слишком узким или проекту нужна более глубокая coverage
в этой зоне.

## Чеклист benchmark evidence

Полезная доказательная база benchmark-проверки должна показывать:

- точную команду, которая была запущена
- выбранный домен и benchmark pack
- локальные outputs инструментов или сохранённые артефакты
- якоря отчёта, совпадающие с ожидаемой формой
- confidence и границы ручной проверки
- replay, сводку сохранённого запуска, Markdown-отчёт или SARIF-путь для проверки
- чёткое разделение локальной доказательной базы и интерпретации модели

Встроенные golden cases - это безопасные синтетические проверки формы отчёта,
маршрутизации pack и границ доказательной базы:

| Кейс | Домен | Ожидаемый фокус проверки |
| --- | --- | --- |
| `ecc-secp256k1-domain-completeness` | ECC | Предположения по домену кривой, полнота метаданных, ограниченная уверенность. |
| `ecc-25519-subgroup-hygiene` | ECC | Subgroup/cofactor, twist hygiene, оговорки по encoding. |
| `ecc-secp256k1-point-format-edge` | ECC | Проверка формата точек и границ parser/encoding. |
| `contract-vault-permission-lane` | Smart contracts | Права vault, внешне достижимый value flow, finding cards. |
| `contract-governance-timelock-lane` | Smart contracts | Управление, timelock, контроль upgrade и emergency-lane review. |
| `contract-repo-scale-lending-protocol` | Smart contracts | Инвентаризация репозитория, protocol lanes, liquidation/collateral/accounting review. |

Отсутствующие секции тоже полезны. Они могут означать, что входные данные не
оправдали этот маршрут проверки, выбранный pack был слишком узким, локальный
toolchain не установлен или отчёт остался осторожным из-за недостатка
доказательной базы.

## Repo-scale путь для смарт-контрактов

Для локального репозитория контрактов начни с ограниченного запуска:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for externally reachable value flow, admin controls, and repo-scale review lanes."
```

Потом можно сравнивать результат с сохранённой baseline-сессией:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the bounded audit and record before/after deltas against the saved baseline session."
```

Что смотреть в результате:

- инвентаризацию контрактов и repo-scale карту протокола
- маршруты обзора по entrypoint-файлам
- приоритеты семейств функций
- покрытие casebook и benchmark
- strongest priorities и строки с остаточным риском
- статус компиляции и состояние внешних анализаторов, если они установлены
- before/after delta и regression flags, если передана baseline-сессия

## ECC путь

Для ECC-оценки сначала полезно посмотреть маршрутизацию и пакеты:

```powershell
python -m app.main --show-routing
python -m app.main --list-packs
```

Затем запустить ограниченный ECC prompt:

```powershell
python -m app.main "Inspect whether secp256k1 point encoding, curve metadata, and local consistency checks produce review-worthy defensive signals."
```

Что смотреть в результате:

- покрытие кривых и семейств
- обработку point format и domain parameters
- subgroup/cofactor и twist-hygiene сигналы
- локальные вычислительные данные отдельно от интерпретации агентов
- confidence calibration и границы ручной проверки
- benchmark posture и regression-watch строки

## Оценка с реальными провайдерами

Hosted-провайдеры необязательны. Их стоит настраивать только если нужно
проверить агентный цикл с живыми ответами модели вместо стандартного `mock`
провайдера.

Поддерживаемые имена провайдеров:

- `openai`
- `openrouter`
- `gemini`
- `anthropic`
- `mock`

Ограниченный live smoke запускать только со своим ключом:

```powershell
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

Оценка с провайдером все равно должна опираться на локальную доказательную
базу, артефакты, границы отчёта и воспроизводимость. Вывод модели сам по себе
не считается доказательством.

## Как выглядит хорошая оценка

Полезная оценка должна ответить:

- запускается ли проект чисто в локальной среде
- остаются ли отчёты осторожными и привязанными к доказательствам
- дают ли benchmark и golden cases стабильный, просматриваемый результат
- отделяются ли smart-contract repo-scale сигналы от ручных выводов
- ограничены ли ECC сигналы локальными вычислениями и явной неопределенностью
- достаточно ли воспроизводимы артефакты и export-слой
- ясны ли коммерческие границы до product, hosted, OEM, white-label или resale
  использования

## Коммерческая граница

Оценка, исследование, внутренняя проверка и локальное тестирование доступны по
условиям публичной лицензии.

Если сценарий включает конкурирующее коммерческое использование, hosted или
managed service, SaaS/platform deployment, OEM-дистрибуцию, white-label,
перепродажу или интеграцию в коммерческую security-платформу, лучше связаться
до запуска, продажи или развертывания.

См.:

- [LICENSE](../../LICENSE)
- [LICENSE_FAQ.ru.md](LICENSE_FAQ.ru.md)
- [COMMERCIAL_LICENSE.ru.md](COMMERCIAL_LICENSE.ru.md)
- [LICENSE_TRANSITION.ru.md](LICENSE_TRANSITION.ru.md)
- [SECURITY.ru.md](SECURITY.ru.md)

## Контакт

- Email: `stelmak159@gmail.com`
- Telegram: `@ECDS4`
- Репозиторий: `https://github.com/ECD5A/EllipticZero`
