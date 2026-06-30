# Практический пример: reentrancy-кейс SmartBugs

Этот пример показывает один воспроизводимый цикл проверки EllipticZero:

1. обнаружить размеченное семейство legacy reentrancy в зафиксированном внешнем
   датасете
2. сохранить локальную сессию и доказательную базу
3. применить ограниченный пример исправления
4. сравнить новый запуск с сохранённым базовым запуском
5. оставить видимыми остаточные сигналы и границы ручной проверки

Это пример оценки продукта, а не доказательство эксплуатируемости или завершённый аудит.

## Цель

| Поле | Значение |
| --- | --- |
| Датасет | [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) |
| Коммит | `230e649123477eff332742a59a1c7cc6dc286cab` |
| Уязвимый исходный файл | `dataset/reentrancy/reentrancy_simple.sol` |
| Метка датасета | `reentrancy` |
| Исправленный контроль | `examples/case_studies/smartbugs_reentrancy/HardenedReentrancyVault.sol` |

EllipticZero не включает внешний датасет в репозиторий и не запускает из него
код. Проверяющий клонирует зафиксированную ревизию и передаёт проекту локальный путь.

## Целевая проверка

```powershell
git clone --filter=blob:none --no-checkout https://github.com/smartbugs/smartbugs-curated.git .test_runs\smartbugs-curated
git -C .test_runs\smartbugs-curated fetch --depth 1 origin 230e649123477eff332742a59a1c7cc6dc286cab
git -C .test_runs\smartbugs-curated checkout --detach 230e649123477eff332742a59a1c7cc6dc286cab

python scripts\validate_smartbugs_subset.py `
  --dataset-root .test_runs\smartbugs-curated `
  --require-pinned-commit `
  --format markdown `
  --output .test_runs\smartbugs-validation.md
```

Результат на зафиксированном наборе:

| Метрика | Результат | Основание |
| --- | ---: | ---: |
| Recall | `100.00%` | 5 размеченных положительных кейсов |
| Miss rate | `0.00%` | 5 размеченных положительных кейсов |
| Целевой false-positive rate | `0.00%` | 1 синтетический отрицательный контроль |
| Результат кейсов | `6/6` | 5 положительных и 1 отрицательный |

False-positive rate относится только к включённому синтетическому контролю.
Его нельзя переносить на произвольные Solidity-репозитории.

## Полная сессия проверки

Запусти проверку уязвимого исходного файла через обычный путь EllipticZero:

```powershell
python -m app.main `
  --lang ru `
  --domain smart_contract_audit `
  --contract-file .test_runs\smartbugs-curated\dataset\reentrancy\reentrancy_simple.sol `
  --pack contract_static_benchmark_pack `
  "Проверь размеченный legacy reentrancy-кейс, сохрани локальную доказательную базу и определи минимальную перепроверку после исправления."
```

Сохрани путь `Stored Session`, который напечатает команда. Затем сравни
локальный исправленный пример с этим базовым запуском:

```powershell
python -m app.main `
  --lang ru `
  --domain smart_contract_audit `
  --contract-file examples\case_studies\smartbugs_reentrancy\HardenedReentrancyVault.sol `
  --pack contract_static_benchmark_pack `
  --compare-session artifacts\sessions\<baseline-session>.json `
  "Перепроверь исправленный withdrawal-путь относительно сохранённой baseline: reentrancy, accounting после внешнего вызова и unchecked low-level call."
```

Если нужны проверки с компиляцией, установи подходящие версии компилятора:

```powershell
python scripts\bootstrap_smart_contract_toolchain.py --solc-version 0.4.15 --solc-version 0.8.24
```

## Полученная доказательная база

Уязвимый запуск дал локальные сигналы для:

- reentrancy-adjacent последовательности в `withdrawBalance`
- обновления accounting после внешней передачи значения
- непроверенного legacy low-level call
- точных подсказок по строкам withdrawal-пути

Исправленный запуск:

- успешно скомпилировался с Solidity `0.8.24`
- перенёс обновление accounting до внешней передачи
- добавил защиту от вложенного входа
- проверил результат low-level call
- убрал целевые семейства reentrancy, post-call accounting и unchecked call

Сравнение с сохранённым базовым запуском показало два улучшения, отсутствие
регрессий, сокращение пунктов ручной проверки с шести до двух и приоритетных
находок с четырёх до нуля. Уровень уверенности остался
`manual_review_required`.

Slither сохранил информационный сигнал `low-level-calls` для исправленного
примера. EllipticZero оставил его в отчёте и не выдал улучшение before/after за
доказательство полной безопасности контракта.

## Что показывает пример

Пример связывает размеченный внешний кейс, локальные сигналы детектора,
структурированный агентами отчёт, пакет воспроизводимости и перепроверку до и
после исправления. Он не доказывает полное покрытие SmartBugs, эксплуатируемость
в рабочей среде или отсутствие других уязвимостей.
