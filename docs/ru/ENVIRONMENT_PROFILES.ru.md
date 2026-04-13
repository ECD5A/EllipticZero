# Профили окружения

EllipticZero можно оценивать в нескольких режимах. Лучше начинать с малого, а
потом подключать внешних провайдеров или локальные security tools только тогда,
когда они действительно нужны.

## Быстрая матрица

| Профиль | Для чего | Требуется | Опционально | Проверка |
|---|---|---|---|---|
| `mock` | первый запуск, просмотр CLI, базовая воспроизводимость | Python 3.11+, установка проекта | ничего | `python -m app.main --doctor` |
| `hosted-agent` | оценка реальной агентной работы с настроенными провайдерами | Python 3.11+, API-ключ провайдера | маршрутизация ролей по моделям | `python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto` |
| `ecc-focused` | ECC metadata, encoding, subgroup, cofactor и family-depth review | Python 3.11+, lab extras | SageMath | `python -m app.main --pack ecc_family_depth_benchmark_pack "Review ECC assumptions."` |
| `smart-contract-static` | Solidity/Vyper parse, compile, static review и benchmark packs | Python 3.11+, smart-contract extras, managed `solc` | Slither, Foundry, Echidna | `.\scripts\setup_local_lab.ps1 -Profile smart-contract-static` |
| `repo-scale-audit` | инвентаризация протокольного репозитория, casebooks, review lanes, сравнение до/после | `smart-contract-static`, локальное дерево контрактов | Slither, Foundry, Echidna | `python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Review repo lanes."` |
| `full-local-lab` | широкий локальный research по ECC, symbolic checks, smart-contract review, replay и bundles | Python 3.11+, `.[lab]` extras | SageMath, Slither, Foundry, Echidna, API-ключ провайдера | `.\scripts\setup_local_lab.ps1` |

## Детали профилей

### `mock`

Используй этот профиль, когда нужно оценить workflow без API-ключей.

Что он дает:

- детерминированное поведение локального mock-провайдера
- CLI и интерактивный walkthrough
- `doctor` / self-check
- генерацию локальных артефактов
- replay и проверку документации

Полезные команды:

```powershell
python -m app.main --doctor
python -m app.main --interactive
python -m app.main --list-packs
```

### `hosted-agent`

Используй этот профиль, когда нужно оценить поведение реальных hosted models.
Проект поддерживает `openai`, `openrouter`, `gemini` и `anthropic`, если
настроен соответствующий API-ключ.

Что он дает:

- реальную агентную работу вместо mock-ответов
- общий provider/model для всех ролей
- опциональную маршрутизацию отдельных ролей по своим provider/model
- hosted smoke checks с тайм-аутом и лимитом токенов запроса

Пример:

```powershell
$env:OPENROUTER_API_KEY="local-key-here"
python -m app.main --provider openrouter "Review whether the local evidence is sufficient for this bounded research lead."
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

### `ecc-focused`

Используй этот профиль для защитных ECC-исследований. SageMath полезен, если он
установлен, но базовый локальный путь может работать через Python-зависимости
из lab-профиля.

Что он дает:

- проверки curve metadata и локального registry
- инспекцию point/public-key format
- ECC consistency checks
- benchmark packs для ECC family-depth, subgroup hygiene и domain completeness
- осторожные секции отчета для residual risk, review queue и exit criteria

Полезные команды:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions."
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, and twist-hygiene assumptions."
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review curve-domain completeness and registry assumptions."
```

### `smart-contract-static`

Используй этот профиль для ограниченного разбора смарт-контрактов, compile
checks, static review и benchmark-pack запусков.

Что он дает:

- вход через Solidity/Vyper файл или inline code
- parser и surface summaries
- управляемый Solidity-компилятор в `.ellipticzero/tooling/solcx`
- опциональные адаптеры Slither, Foundry и Echidna, если они установлены локально
- benchmark-pack summaries и review queues

Установка:

```powershell
.\scripts\setup_local_lab.ps1 -Profile smart-contract-static
```

Полезная команда:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

### `repo-scale-audit`

Используй этот профиль, когда файл контракта находится внутри локального дерева
протокола. EllipticZero может построить ограниченную инвентаризацию, вывести
review lanes, сопоставить casebook-семейства и подключить baseline-сравнение.

Что он дает:

- разделение first-party и dependency scope
- repo inventory и entrypoint review lanes
- protocol-style casebook matches
- приоритизацию function-family и risk-family
- сравнение до/после по сохраненным sessions, manifests или bundles

Полезные команды:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run and compare against the saved baseline."
```

### `full-local-lab`

Используй этот профиль, когда нужна самая широкая локальная среда. Он ставит
`lab` extra и разворачивает управляемые версии Solidity-компилятора, если это
не отключено явно.

Установка:

```powershell
.\scripts\setup_local_lab.ps1
```

Что проверить после установки:

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m ruff check .
python -m compileall app tests scripts
pytest -q
```

## Опциональные локальные инструменты

EllipticZero деградирует осторожно, если опциональные инструменты недоступны.
Отсутствующие инструменты должны отображаться в `doctor` и в confidence notes
отчета, а не считаться успешной доказательной базой.

| Инструмент | Для чего | Обязателен по умолчанию? |
|---|---|---|
| `solc` / managed `py-solc-x` | compile checks для Solidity | managed path разворачивается setup-профилями |
| `slither` | внешний static-analysis adapter | опционально |
| `forge` | Foundry-oriented local checks | опционально |
| `echidna` | property/fuzz-oriented smart-contract checks | опционально |
| `sage` | advanced symbolic и ECC math paths | опционально |

## Ключи провайдеров

Hosted providers опциональны. Не коммить API-ключи.

Поддерживаемые переменные окружения:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Используй `.env.example` как шаблон для локальной настройки.
