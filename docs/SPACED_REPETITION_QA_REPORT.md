# QA Report: Spaced Repetition

Date: 2026-03-31
Project: Deckly
Area: backend spaced repetition / study session flow

## Scope

Проверка выполнена по следующим направлениям:

- начальное состояние карточки
- learning phase
- relearning phase
- review phase
- переходы состояний
- session behavior
- граничные случаи
- корректность обновления данных в БД
- UX-логика кнопок `again` / `hard` / `good` / `easy`

## Verification Summary

- Полный прогон тестов: `96 passed`
- Coverage: `92.12%`
- Базовая логика scheduler-а выглядит корректной
- Критичных дефектов в ядре интервального повторения не обнаружено

Основные риски находятся не в самих формулах роста интервалов, а в orchestration вокруг study sessions и устойчивости к поврежденным данным.

## Found Bugs

### Medium

#### 1. Активная сессия игнорирует новые `limit` и `new_cards_limit`

При наличии уже созданной active session она переиспользуется только по `(user, deck, mode, shuffle_cards)`. Новые `limit` и `new_cards_limit` при повторном запросе сессии не учитываются.

Эффект:

- пользователь может запросить более короткую сессию
- система вернет старый набор карточек
- поведение API становится неочевидным

Код:

- `backend/spaced_repetition.py:545`
- `backend/spaced_repetition.py:559`

#### 2. `decode_card_order()` неустойчив к валидному JSON неправильной структуры

Сейчас обработка защищена только от синтаксически битого JSON. Если в `card_order` попадет валидный JSON, но не массив, например:

- `"{}"`
- `"1"`
- `"null"`

то возможны `TypeError` / `ValueError` при последующем разборе.

Эффект:

- сборка или продолжение сессии может упасть на поврежденных данных
- нет graceful fallback на пустой `card_order`

Код:

- `backend/spaced_repetition.py:94`
- `backend/spaced_repetition.py:99`

### Minor

#### 3. Пустая сессия сохраняется как активная незавершенная запись

Если `build_study_session()` собрал пустой список карточек, запись сессии все равно создается с `completed_at = NULL`. Формально она выглядит активной до следующего запроса, где будет закрыта постфактум.

Эффект:

- в БД появляются пустые active sessions
- семантика `completed_at` получается не совсем точной

Код:

- `backend/spaced_repetition.py:558`
- `backend/spaced_repetition.py:570`
- `backend/spaced_repetition.py:548`

## Risky Logic Areas

### Medium

#### 1. Недостаточное покрытие session edge cases

Функционально не покрыты отдельными тестами:

- `review_all`
- `limited`
- `limit`
- `new_cards_limit`
- `shuffle_cards`
- пустая сессия
- `current_index > len(card_order)`
- deleted cards внутри уже сохраненного `card_order`

Это не означает, что логика сломана, но именно здесь сейчас наибольший остаточный риск.

Код:

- `backend/spaced_repetition.py:494`
- `backend/spaced_repetition.py:496`
- `backend/spaced_repetition.py:521`
- `backend/spaced_repetition.py:549`
- `backend/spaced_repetition.py:561`
- `backend/spaced_repetition.py:632`

### Minor

#### 2. `hard` в relearning может ощущаться слишком резким

Для `RELEARNING_STEPS = [10m, 1d]` кнопка `hard` использует midpoint между шагами. На первом relearning step это примерно `12h 05m`.

Технически логика консистентна, но с UX-точки зрения это может быть слишком большой скачок после lapse.

Код:

- `backend/spaced_repetition.py:20`
- `backend/spaced_repetition.py:361`

#### 3. Состояние `new` создается лениво

`UserCardState` создается не в момент появления карточки у пользователя, а при первом review/session обращении.

Это не баг, но важно для ожиданий:

- логически карточка считается `new`
- физическая запись в `user_card_state` может еще не существовать

Код:

- `backend/spaced_repetition.py:232`

## What Was Checked

### 1. Initial State

Проверено:

- новая карточка получает статус `new`
- `due_at` инициализируется текущим временем
- стартовые параметры выставляются корректно:
  - `ease_factor = 2.5`
  - `difficulty = 2.5`
  - `stability = 0.0`
  - `scheduled_days = 0.0`
  - `elapsed_days = 0.0`
  - `reps = 0`
  - `lapses = 0`
  - `learning_step = 0`

Код:

- `backend/spaced_repetition.py:244`
- `backend/spaced_repetition.py:260`

### 2. Learning Phase

Проверено:

- `again` возвращает на первый learning step
- `hard` оставляет в learning и дает промежуточную задержку
- `good` переводит на следующий learning step
- `easy` сразу выпускает в review с увеличенным стартовым интервалом `3.0` дня
- learning phase не меняет `ease_factor`

Код:

- `backend/spaced_repetition.py:395`
- `backend/spaced_repetition.py:420`

Тесты:

- `tests/test_main.py:350`
- `tests/test_main.py:375`
- `tests/test_main.py:675`
- `tests/test_main.py:700`

### 3. Relearning Phase

Проверено:

- провал review переводит карточку в `relearning`
- `lapses` увеличивается
- `ease_factor` уменьшается на `0.2`
- шаги relearning работают через `10m -> 1d`
- после успешного relearning карточка возвращается в review

Код:

- `backend/spaced_repetition.py:430`
- `backend/spaced_repetition.py:441`
- `backend/spaced_repetition.py:417`

Тесты:

- `tests/test_main.py:726`
- `tests/test_main.py:957`

### 4. Review Phase

Проверено:

- `hard` дает более осторожный рост
- `good` дает базовый рост
- `easy` дает более агрессивный рост
- интервалы хранятся как `float` без раннего округления вверх
- `ease_factor` обновляется и ограничивается диапазоном `1.3 .. 2.8`
- `elapsed_days` участвует в расчете якоря интервала

Код:

- `backend/spaced_repetition.py:369`
- `backend/spaced_repetition.py:392`
- `backend/spaced_repetition.py:423`
- `backend/spaced_repetition.py:457`

Тесты:

- `tests/test_main.py:419`
- `tests/test_main.py:461`
- `tests/test_main.py:504`
- `tests/test_main.py:547`
- `tests/test_main.py:590`
- `tests/test_main.py:633`
- `tests/test_main.py:772`

### 5. State Transitions

Проверено:

- `new -> learning`
- `learning -> review`
- `review -> relearning`
- `relearning -> review`

Также проверено, что переходы не ломают:

- `reps`
- `lapses`
- `learning_step`
- `scheduled_days`
- `due_at`
- `last_reviewed_at`
- `updated_at`

Код:

- `backend/spaced_repetition.py:341`
- `backend/spaced_repetition.py:348`
- `backend/spaced_repetition.py:470`

### 6. Session Behavior

Проверено:

- в режиме `interval` карточка при `again/hard` добавляется в конец текущей сессии
- `current_index` двигается корректно
- нельзя ответить не на ту карточку, которая ожидается в `current session order`
- сессия резюмируется с того же `current_index`

Код:

- `backend/spaced_repetition.py:608`
- `backend/spaced_repetition.py:655`

Тесты:

- `tests/test_main.py:853`
- `tests/test_main.py:880`
- `tests/test_main.py:928`
- `tests/test_hardening.py:400`

### 7. Edge Cases

Проверено:

- invalid rating режется на уровне схем
- неправильный `mode`, `limit`, `new_cards_limit` валидируются
- `card_order` с синтаксически битым JSON не падает
- deleted cards исключаются из active cards

Код:

- `backend/schemas.py:205`
- `backend/schemas.py:224`
- `backend/spaced_repetition.py:54`
- `backend/spaced_repetition.py:61`
- `backend/spaced_repetition.py:94`
- `backend/spaced_repetition.py:536`

Тесты:

- `tests/test_schemas.py:122`
- `tests/test_hardening.py:381`

### 8. Database Updates After Review

После каждого ответа обновляются корректно:

- `status`
- `due_at`
- `scheduled_days`
- `learning_step`
- `reps`
- `lapses`
- `ease_factor`
- `last_reviewed_at`
- `updated_at`

Код:

- `backend/spaced_repetition.py:341`
- `backend/spaced_repetition.py:348`
- `backend/spaced_repetition.py:470`
- `backend/review_router.py:75`
- `backend/review_router.py:87`

### 9. UX Logic

Поведение кнопок действительно различается:

- `again` резко сбрасывает в relearning и штрафует `ease_factor`
- `hard` двигает осторожно
- `good` является базовой траекторией
- `easy` дает заметно больший интервал, чем `good`

После lapse рост интервалов действительно становится осторожнее.

Код:

- `backend/spaced_repetition.py:430`
- `backend/spaced_repetition.py:457`

## Recommended Additional Test Cases

### Criticality: Medium

- Проверка повторного запроса study session с другим `limit`
- Проверка повторного запроса study session с другим `new_cards_limit`
- Проверка `card_order = '{}'`
- Проверка `card_order = '1'`
- Проверка `card_order = 'null'`
- Проверка `current_index > len(card_order)` в resume и submit flow
- Проверка deleted card внутри уже сохраненного `card_order`
- Проверка пустой сессии без карточек

### Criticality: Minor

- Проверка `shuffle_cards=True`, что перемешивание происходит один раз на создание сессии
- Проверка `review_all`
- Проверка `limited`
- Проверка `relearning hard`
- Проверка `relearning easy`

## Final Assessment

Система интервального повторения в текущем состоянии выглядит логически корректной и уже достаточно зрелой:

- learning / relearning / review работают последовательно
- состояния переходят ожидаемо
- интервалы различаются по кнопкам осмысленно
- `elapsed_days` реально участвует в планировании
- full test suite проходит успешно

Если коротко:

- ядро scheduler-а: корректно
- session orchestration: есть несколько средних рисков
- edge-case hardening: стоит усилить отдельными тестами и защитой `card_order`
