# Spaced Repetition UX Fixes

Date: 2026-03-31
Source audit: `docs/SPACED_REPETITION_UX_RESEARCH.md`
Project: Deckly

## Summary

Этот документ фиксирует изменения, внесенные по итогам UX-аудита интервального повторения.

Основной фокус текущего набора правок:

- убрать расхождение между interval preview и backend scheduler
- честно развести personal interval review и preview-only shared flow
- убрать test framing из interval summary
- добавить объяснение ratings и состав очереди перед стартом
- дать пользователю контроль над `new_cards_limit`

## Implemented Fixes

### 1. Interval previews теперь строятся из backend scheduler logic

Что сделано:

- в backend добавлен `interval_preview` для `CardOut`
- в backend добавлен `interval_preview` в `ReviewResult`
- preview теперь строится из той же scheduler-логики, что и реальное планирование
- frontend сначала использует серверный preview, а локальный расчет оставлен только как fallback

Результат:

- кнопки `Again / Hard / Good / Easy` больше не обещают устаревшие интервалы
- preview и реальный scheduling используют один контракт ответа API

Код:

- `backend/spaced_repetition.py`
- `backend/schemas.py`
- `backend/review_router.py`

### 2. Shared / guest interval flow теперь явно обозначен как preview-only

Что сделано:

- interval tile динамически меняет copy на `Interval Preview`, если scheduling не персональный
- setup screen показывает `Preview only`
- copy больше не называет shared preview `due queue`
- добавлен CTA на sign-in / save-to-library, чтобы перейти к реальному персональному scheduling
- submit interval ratings больше не пытается отправлять review на backend для preview-only flow

Результат:

- интерфейс больше не притворяется настоящим сохранением интервального повторения там, где его нет

Код:

- `frontend/pages/study/study-render.js`
- `frontend/pages/study/study-controls.js`
- `frontend/pages/study/study-actions.js`
- `frontend/pages/study/study-page.js`

### 3. Interval summary больше не использует accuracy / correct / incorrect framing

Что сделано:

- для interval mode summary переписан в SRS framing
- completion screen показывает:
  - `Again`
  - `Hard`
  - `Good`
  - `Easy`
  - `Repeated Today`
  - `Due Left`
- live stats для interval mode тоже переключены на SRS-метрики

Результат:

- `Hard` больше не выглядит как экзаменационная ошибка
- session feedback теперь описывает scheduling outcome, а не псевдо-тестовый score

Код:

- `frontend/pages/study/study-render.js`
- `frontend/pages/study/study-viewer.js`
- `frontend/pages/study/study.css`

### 4. Добавлено объяснение значений Again / Hard / Good / Easy

Что сделано:

- под rating buttons добавлен help block с operational guidance

Результат:

- меньше когнитивной нагрузки на первом использовании interval mode
- меньше риска, что пользователь будет жать `Good` только чтобы “не портить accuracy”

Код:

- `frontend/pages/study/study-controls.js`
- `frontend/pages/study/study.css`

### 5. Перед стартом interval run теперь виден состав очереди

Что сделано:

- стартовый экран interval mode теперь показывает breakdown очереди:
  - due reviews
  - overdue
  - learning
  - relearning
  - new
- добавлено короткое объяснение, почему карточки попали в текущий run
- если есть незавершенная interval session, стартовый экран предлагает `Resume Interval Review`

Результат:

- queue больше не выглядит как черный ящик

Код:

- `frontend/pages/study/study-session.js`
- `frontend/pages/study/study-render.js`
- `frontend/pages/study/study-page.js`

### 6. В UI добавлен контроль `new_cards_limit`

Что сделано:

- добавлены quick controls `New 0 / 5 / 10 / 20`
- настройка сохранена в study settings
- backend endpoint поддерживает `restart_session`, чтобы interval queue реально пересобиралась под новые настройки

Результат:

- `new_cards_limit` больше не существует только на backend без UI-контроля

Код:

- `backend/deck_study_router.py`
- `backend/spaced_repetition.py`
- `frontend/pages/study/study-session.js`
- `frontend/pages/study/study-controls.js`
- `frontend/pages/study/study-render.js`
- `frontend/pages/study/study-page.js`

### 7. Interval overview в deck view теперь объясняет EF как Ease

Что сделано:

- колонка `EF` переименована в `Ease`
- добавлен `title`, объясняющий смысл колонки

Код:

- `frontend/pages/deck/deck-page.js`
- `frontend/pages/deck/index.html`

### 8. Выровнен язык документа через `lang="en"`

Что сделано:

- страницы study и deck переведены на `lang="en"`, что соответствует текущему UI copy

Код:

- `frontend/pages/study/index.html`
- `frontend/pages/deck/index.html`

## Tests / Verification

Что проверено:

- `node --check frontend/pages/study/study-page.js`
- `node --check frontend/pages/study/study-render.js`
- `node --check frontend/pages/study/study-viewer.js`
- `node --check frontend/pages/study/study-session.js`
- `node --check frontend/pages/study/study-actions.js`
- `node --check frontend/pages/study/study-controls.js`
- `node --check frontend/pages/deck/deck-page.js`
- `python3 -m py_compile backend/schemas.py backend/spaced_repetition.py backend/review_router.py backend/deck_study_router.py tests/test_main.py tests/test_schemas.py`

Добавлены тесты:

- preview в shared study session
- restart interval session с новым `new_cards_limit`
- scheduler-aligned interval preview для review card

Не удалось полноценно прогнать:

- `pytest tests/test_main.py tests/test_schemas.py`

Причина:

- локальная test Postgres отвечает `password authentication failed for user "deckly"`

## Follow-Up

Что осталось за пределами текущего объема:

- полноценные usability sessions и event tracking из research-документа
- более глубокий onboarding / coach marks для first-run SRS behavior
- richer tooltip / glossary around ease factor beyond simple rename to `Ease`
