# Оценка EllipticZero

Этот документ помогает исследователям, командам безопасности, интеграторам и
потенциальным коммерческим партнерам понять, как оценивать EllipticZero без
догадок и лишней возни.

EllipticZero рассчитан на прямую проверку: исходный код, документация, CLI,
локальные артефакты, отчеты, benchmark-пакеты и golden cases должны складываться
в одну понятную картину.

## Что можно оценивать

По условиям публичной лицензии `FSL-1.1-ALv2` репозиторий можно читать,
собирать, запускать локально и оценивать для исследований, внутренней проверки
и других разрешенных целей.

Полезные пути оценки:

- просмотр кода оркестрации, агентных ролей, раннеров, отчетов и границ экспорта
- локальная CLI-проверка без ключей в `mock`-режиме
- golden/synthetic cases для стабильных smoke-проверок
- ECC benchmark-пакеты по point format, curve metadata, subgroup, cofactor,
  twist и domain-completeness поверхностям
- smart-contract audit по parser, compile, repo inventory, casebook, benchmark,
  comparison и manual-review lanes
- проверка с реальными провайдерами на ваших собственных API-ключах
- просмотр session, trace, manifest, bundle и replay-артефактов

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

Для сохраненного запуска можно получить короткую reviewer-сводку без повторного
выполнения:

```powershell
python -m app.main --evaluation-summary --replay-bundle .\artifacts\bundles\session_id
```

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

В первом экране отчёта стоит проверить:

- `Finding Cards` с потенциальной находкой, доказательством, причиной важности, направлением исправления и путём перепроверки
- `Сводка триажа репозитория`, `Сводка ECC-триажа` или `Сводка изменений после доработки`, если входные данные оправдывают такой первый экран
- `Evidence Coverage` с количеством доказательств, tool-backed count, tools, experiment types и review items
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
| Golden cases | Встроенные ECC- и smart-contract кейсы запускаются чисто и дают ожидаемую форму отчета. | Smoke-output стабилен при повторных локальных запусках. |
| ECC coverage | В отчете видны форматы точек, метаданные кривых, subgroup/cofactor проверки, twist hygiene, переходы между семействами кривых, domain-completeness поверхности и компактная сводка ECC-триажа. | Локальные вычисления и интерпретация отчета согласованы без завышения уверенности. |
| Smart-contract coverage | Parser, compile, inventory, repo map, casebook, benchmark pack, review queue, residual-risk lanes и компактная сводка триажа появляются, когда входные данные это оправдывают. | Отчет отделяет подтвержденные локальные сигналы от приоритетов ручной проверки. |
| Comparison | Сохраненную baseline можно подключить через `--compare-session`, `--compare-manifest` или `--compare-bundle`. | Before/after строки и remediation-delta summary показывают осторожные изменения, возможные regression flags и следующий replay-path. |
| Export quality | Session, trace, manifest и bundle artifacts остаются внутри разрешенных локальных export roots. | Проверяющий может воспроизвести запуск, посмотреть evidence trail и быстро увидеть `report_snapshot_summary` в manifest / bundle overview. |
| Hosted path | Optional live smoke работает только когда проверяющий передает валидные provider credentials. | Provider output воспринимается как интерпретация, а не как доказательство. |

Пропуски в scorecard тоже полезны. Если какая-то линия проверки отсутствует, стоит
проверить: входные данные не оправдывали этот путь, локальный toolchain не был
установлен, prompt был слишком узким или проекту нужна более глубокая coverage
в этой зоне.

## Repo-scale путь для смарт-контрактов

Для локального репозитория контрактов начни с ограниченного запуска:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for externally reachable value flow, admin controls, and repo-scale review lanes."
```

Потом можно сравнивать результат с сохраненной baseline-сессией:

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
базу, артефакты, границы отчета и воспроизводимость. Вывод модели сам по себе
не считается доказательством.

## Как выглядит хорошая оценка

Полезная оценка должна ответить:

- запускается ли проект чисто в локальной среде
- остаются ли отчеты осторожными и привязанными к доказательствам
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

## Контакт

- Email: `stelmak159@gmail.com`
- Telegram: `@ECDS4`
- Репозиторий: `https://github.com/ECD5A/EllipticZero`
