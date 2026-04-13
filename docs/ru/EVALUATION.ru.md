# Оценка EllipticZero

Этот документ помогает исследователям, security-командам, интеграторам и
потенциальным коммерческим партнерам понять, как оценивать EllipticZero без
догадок и лишней возни.

EllipticZero рассчитан на прямую проверку: исходный код, документация, CLI,
локальные артефакты, отчеты, benchmark-пакеты и golden cases должны складываться
в одну понятную картину.

## Что можно оценивать

По условиям публичной лицензии `FSL-1.1-ALv2` репозиторий можно читать,
собирать, запускать локально и оценивать для исследований, внутреннего review и
других разрешенных целей.

Полезные пути оценки:

- просмотр кода оркестрации, агентных ролей, раннеров, отчетов и export-границ
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

Machine-readable сводка для автоматической проверки:

```powershell
python -m app.main --evaluation-summary --evaluation-summary-format json
```

Посмотреть встроенные golden cases:

```powershell
python -m app.main --list-golden-cases
```

Запустить ECC golden case:

```powershell
python -m app.main --golden-case ecc-secp256k1-point-format-edge
```

Запустить repo-scale smart-contract golden case:

```powershell
python -m app.main --golden-case contract-repo-scale-lending-protocol
```

## Benchmark scorecard

Benchmark-слой стоит воспринимать как проверочный список для оценки, а не как
обещание, что инструмент сам полностью проаудировал цель.

| Зона | Что проверять | Более сильный сигнал |
| --- | --- | --- |
| Golden cases | Встроенные ECC и smart-contract cases запускаются чисто и дают ожидаемую форму отчета. | Smoke-output стабилен при повторных локальных запусках. |
| ECC coverage | В отчете видны форматы точек, метаданные кривых, subgroup/cofactor проверки, twist hygiene, переходы между семействами кривых и domain-completeness поверхности. | Локальные вычисления и интерпретация отчета согласованы без завышения уверенности. |
| Smart-contract coverage | Parser, compile, inventory, repo map, casebook, benchmark pack, review queue и residual-risk lanes появляются, когда входные данные это оправдывают. | Отчет отделяет подтвержденные локальные сигналы от приоритетов ручной проверки. |
| Comparison | Сохраненную baseline можно подключить через `--compare-session`, `--compare-manifest` или `--compare-bundle`. | Before/after строки показывают осторожные изменения и возможные regression flags. |
| Export quality | Session, trace, manifest и bundle artifacts остаются внутри разрешенных локальных export roots. | Проверяющий может воспроизвести запуск и посмотреть evidence trail. |
| Hosted path | Optional live smoke работает только когда evaluator передает валидные provider credentials. | Provider output воспринимается как интерпретация, а не как доказательство. |

Пропуски в scorecard тоже полезны. Если какой-то lane отсутствует, стоит
проверить: входные данные не оправдывали этот lane, локальный toolchain не был
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

- inventory контрактов и repo-scale карту протокола
- entrypoint review lanes
- приоритеты семейств функций
- покрытие casebook и benchmark
- strongest priorities и residual-risk строки
- статус компиляции и posture внешних анализаторов, если они установлены
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
проверить агентный цикл с живыми model outputs вместо стандартного `mock`
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

Оценка, исследование, внутренний review и локальное тестирование доступны по
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
