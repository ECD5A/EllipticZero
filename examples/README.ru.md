# Примеры EllipticZero

Эти примеры рассчитаны на безопасный, ограниченный и воспроизводимый запуск.
По умолчанию они работают в локальном `mock`-режиме, если внешний провайдер не
настроен явно.

Не вставляй API-ключи в issues, коммиты, скриншоты или переписку. Ключи стоит
задавать только в локальной оболочке или локальном `.env`.

Сокращённые формы отчётов смотри в [SAMPLE_OUTPUTS.ru.md](SAMPLE_OUTPUTS.ru.md).
Воспроизводимые синтетические evaluator cases смотри в
[golden_cases/README.ru.md](golden_cases/README.ru.md).

Быстрый evaluator path:

```powershell
python -m app.main --list-golden-cases
python -m app.main --golden-case contract-repo-scale-lending-protocol
python -m app.main --golden-case ecc-secp256k1-point-format-edge
```

## Проверка готовности

```powershell
python -m app.main --doctor
python -m app.main --list-packs
python -m app.main --show-routing
```

## Аудит смарт-контрактов

Ограниченный обзор inline Solidity:

```powershell
python -m app.main --domain smart_contract_audit --contract-code "pragma solidity ^0.8.20; contract Vault { mapping(address => uint256) public balances; }" "Review reachable state, value-flow, and externally visible surfaces."
```

Ограниченный обзор локального файла контракта:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol "Audit the contract for low-level call review surfaces and externally reachable value flow."
```

Static benchmark pack для локального файла контракта:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack contract_static_benchmark_pack "Benchmark the contract with bounded static analysis and parser-to-surface cross-checks."
```

Repo-casebook benchmark, если контракт находится внутри локального дерева протокола:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --pack repo_casebook_benchmark_pack "Compare the bounded repo inventory against supported protocol-style review lanes."
```

## ECC-исследования

Прямая ограниченная ECC-сессия:

```powershell
python -m app.main "Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output."
```

ECC family-depth benchmark pack:

```powershell
python -m app.main --pack ecc_family_depth_benchmark_pack "Review curve-family transitions, parameter labels, and encoding assumptions for defensive ECC analysis."
```

Проверки subgroup/cofactor hygiene:

```powershell
python -m app.main --pack ecc_subgroup_hygiene_benchmark_pack "Review subgroup, cofactor, and twist-hygiene assumptions under bounded local checks."
```

Проверки domain completeness:

```powershell
python -m app.main --pack ecc_domain_completeness_benchmark_pack "Review whether curve-domain assumptions are complete enough for a cautious defensive report."
```

## Проверка до/после

Привязать сохранённую baseline-сессию к новому ограниченному запуску:

```powershell
python -m app.main --domain smart_contract_audit --contract-file .\contracts\Vault.sol --compare-session .\artifacts\sessions\baseline.json "Re-run the scoped audit and record before/after deltas against the saved baseline session."
```

Повторить уже сохранённую сессию:

```powershell
python -m app.main --replay-session .\artifacts\sessions\session_id.json
```

## Smoke test внешнего провайдера

Этот раздел нужен только если у тебя уже есть локальный API-ключ.

OpenAI:

```powershell
$env:OPENAI_API_KEY="local-key-here"
python -m app.main --live-provider-smoke openai --live-smoke-model gpt-4.1-mini
```

OpenRouter:

```powershell
$env:OPENROUTER_API_KEY="local-key-here"
python -m app.main --live-provider-smoke openrouter --live-smoke-model openrouter/auto
```

## Артефакты

Завершённые запуски могут записывать сессии, трассировки, сравнительные
результаты, манифесты и bundle-пакеты в `artifacts/`. Сохраняй эти артефакты,
когда нужна воспроизводимая доказательная база, и удаляй чувствительные
локальные входные данные перед публикацией отчётов.
