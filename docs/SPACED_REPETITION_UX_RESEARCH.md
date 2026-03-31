# UX Research: Spaced Repetition System

Date: 2026-03-31
Project: Deckly
Area: study flow / interval review / schedule transparency
Research type: heuristic UX audit of the current implementation

## What This Report Is

Это не классическое полевое UX-исследование с интервью, аналитикой и usability sessions.

Это полный heuristic UX audit текущей системы интервального повторения на основе:

- продуктового сценария пользователя
- фронтенд-реализации study flow
- backend/API логики интервального повторения
- текстов, feedback loops и состояния интерфейса
- QA-проверки scheduler-а и session behavior

## Files Reviewed

- `frontend/pages/study/index.html`
- `frontend/pages/study/study-page.js`
- `frontend/pages/study/study-session.js`
- `frontend/pages/study/study-controls.js`
- `frontend/pages/study/study-actions.js`
- `frontend/pages/study/study-render.js`
- `frontend/pages/study/study-viewer.js`
- `frontend/pages/deck/index.html`
- `frontend/pages/deck/deck-page.js`
- `frontend/pages/home/index-page.js`
- `backend/deck_study_router.py`
- `backend/deck_share_router.py`
- `backend/review_router.py`
- `backend/spaced_repetition.py`
- `backend/schemas.py`

## Executive Summary

Система интервального повторения уже выглядит сильнее среднего по прозрачности:

- есть отдельный study hub
- есть выделенный interval mode
- есть preview следующих интервалов на кнопках
- есть word list с текущим статусом карточек
- есть focus mode, клавиатурные шорткаты и понятный visual flow

Но сейчас UX ломается в самом важном месте: там, где пользователь должен доверять scheduler-у.

Главные проблемы:

1. UI показывает прогнозы интервалов, которые уже не совпадают с реальным backend scheduler-ом.
2. Interval mode для гостя выглядит как “настоящий spaced repetition”, хотя фактически ничего не сохраняет и не планирует.
3. Interval review в интерфейсе подается как “accuracy / correct / incorrect”, хотя SRS-режим не должен ощущаться как тест с правильными и неправильными ответами.
4. Пользователю не объясняют, чем реально отличаются `Again`, `Hard`, `Good`, `Easy`.
5. У пользователя почти нет контроля над составом interval queue, хотя backend часть это уже умеет.

Если коротко:

- scheduler как система планирования уже хороший
- UX-оболочка вокруг него пока еще не полностью соответствует его логике
- основной риск сейчас в потере доверия пользователя к кнопкам, прогнозам и смыслу интервалов

## Current Experience Map

### 1. Discovery

На home dashboard пользователь видит число карточек “to review today” и может быстро перейти в study.

Что работает хорошо:

- есть заметный CTA `Study`
- есть агрегированный due count
- есть быстрый вход в deck study hub

Что слабее:

- “today review count” хорошо работает как trigger, но не объясняет, что именно считается due
- нет различия между new / learning / review прямо на dashboard

Код:

- `frontend/pages/home/index-page.js:127`
- `frontend/pages/home/index-page.js:136`

### 2. Deck Study Hub

Study hub дает пользователю 4 режима:

- `Review All`
- `Review Count`
- `Interval Review`
- `Test Mode`

Что работает хорошо:

- режимы отделены визуально и концептуально
- interval mode не спрятан, а подан как отдельная сущность
- есть ощущение “control center” вместо линейного тренажера

Что слабее:

- между режимами мало образовательного контекста
- пользователю не объясняется, когда лучше использовать `Interval Review`, а когда `Review All`
- часть системы выглядит “advanced”, но без объяснения принципов

Код:

- `frontend/pages/study/study-page.js:57`
- `frontend/pages/study/index.html:59`

### 3. Interval Session Start

Перед стартом interval mode пользователь видит only:

- заголовок `Interval Review Queue`
- число карточек в due queue
- кнопку `Start Interval Review`

Что работает хорошо:

- стартовый шаг простой
- нет перегрузки настройками

Что слабее:

- слишком мало контекста про состав очереди
- не видно, сколько там:
  - new cards
  - relearning cards
  - overdue review cards
- не видно, по какому правилу карточки попали в текущую сессию
- нет настройки `new cards limit`, хотя backend это поддерживает

Код:

- `frontend/pages/study/study-render.js:93`
- `backend/deck_study_router.py:14`

### 4. In-Session Recall Decision

После раскрытия ответа пользователь видит 4 кнопки:

- `Again`
- `Hard`
- `Good`
- `Easy`

Плюс маленькие preview следующего появления.

Это один из самых важных UX-узлов во всем продукте.

Что работает хорошо:

- rating buttons визуально разделены
- есть keyboard mapping `1/2/3/4`
- есть next-interval preview прямо под действием
- flow “show answer -> rate recall” соответствует ментальной модели SRS

Что слабее:

- нет объяснения semantics кнопок
- пользователь должен сам догадаться, чем `Hard` отличается от `Again`
- preview интервала воспринимается как обещание системы, а сейчас это обещание не всегда правдиво

Код:

- `frontend/pages/study/study-controls.js:233`
- `frontend/pages/study/study-page.js:548`

### 5. Completion Feedback

После interval session пользователь видит completion screen с:

- `Accuracy`
- `mastered`
- `need review`
- `correct / incorrect`

Это хорошо подходит self-check / test mode, но плохо подходит настоящему SRS.

Почему:

- `Hard` в review обычно означает “вспомнил, но тяжело”
- это не “ошибка” в смысле теста
- пользователь в SRS ожидает scheduling feedback, а не экзаменационную оценку

Код:

- `frontend/pages/study/study-actions.js:192`
- `frontend/pages/study/study-actions.js:196`
- `frontend/pages/study/study-viewer.js:165`
- `frontend/pages/study/study-viewer.js:193`

## Strengths

### 1. Хорошая прозрачность системы

Отдельная interval tab в deck view показывает:

- статус карточки
- interval
- next appearance
- last review
- EF

Это очень сильная сторона. Пользователь не чувствует, что scheduler “что-то магически делает в фоне”.

Код:

- `frontend/pages/deck/index.html:158`
- `frontend/pages/deck/deck-page.js:277`

### 2. Хорошая глубина interaction design

В study flow уже есть:

- fullscreen focus mode
- flip interaction
- keyboard shortcuts
- undo last answer
- completion actions
- fast transition between deck list and study

Это добавляет ощущение зрелого продукта, а не сырого CRUD-интерфейса.

### 3. Архитектурно сильная база для дальнейшего UX

Backend уже умеет:

- различать learning / review / relearning
- считать `elapsed_days`
- строить real due queue
- обновлять progress
- принимать review ratings как отдельную модель

То есть UX можно сильно улучшать без полной переделки scheduler-а.

## Findings

## Critical / High

### 1. Interval previews в UI уже не соответствуют реальному scheduler-у

Это сейчас самая опасная UX-проблема.

Пользователь видит на кнопках обещание следующего интервала, но фронтенд считает preview по старой логике:

- `RELEARNING_STEPS_MS` во фронте все еще `[10m]`, хотя backend уже `[10m, 1d]`
- learning `easy` во фронте все еще выглядит как `1 day`, хотя backend уже `3 days`
- review previews во фронте все еще используют старый расчет через `ceil(base * EF)`
- во фронтенде нет:
  - `hard` multiplier
  - `easy` multiplier
  - учета `elapsed_days`
  - осторожного overdue bonus

Из-за этого кнопки могут обещать одно, а после нажатия система реально поставить другое.

UX-эффект:

- падает доверие к scheduler-у
- пользователь не может “научиться” системе
- кнопки ощущаются случайными
- интервал preview перестает быть decision aid и превращается в misleading hint

Frontend:

- `frontend/pages/study/study-session.js:10`
- `frontend/pages/study/study-session.js:11`
- `frontend/pages/study/study-session.js:148`
- `frontend/pages/study/study-session.js:162`
- `frontend/pages/study/study-session.js:178`

Backend:

- `backend/spaced_repetition.py:369`
- `backend/spaced_repetition.py:381`
- `backend/spaced_repetition.py:395`
- `backend/spaced_repetition.py:423`

Recommendation:

- вынести preview logic в общий shared contract
- либо считать preview на сервере
- либо синхронизировать JS-алгоритм 1:1 с backend и покрыть это contract-тестами

### 2. Гостевой interval mode выглядит как настоящий SRS, но фактически ничего не сохраняет

Для неавторизованного пользователя или shared study flow:

- interval mode доступен визуально
- есть `Again / Hard / Good / Easy`
- есть interval previews
- есть due queue

Но фактически:

- сервер возвращает shared preview как `review_all`
- там нет персонального card state
- review ratings не отправляются на backend для гостей
- requeue/interval scheduling по-настоящему не работают

То есть UI обещает “interval repetition”, а поведение ближе к read-only demo / self-check.

UX-эффект:

- пользователь думает, что учится “по системе”
- но прогресс не сохраняется
- интервалы не персонализируются
- модель продукта становится нечестной

Frontend:

- `frontend/pages/study/study-session.js:320`
- `frontend/pages/study/study-actions.js:167`
- `frontend/pages/study/study-actions.js:191`

Backend:

- `backend/deck_share_router.py:26`
- `backend/deck_share_router.py:42`
- `backend/deck_share_router.py:71`

Recommendation:

- либо скрыть / заблокировать настоящий interval mode для гостя
- либо честно переименовать его в preview mode
- либо показывать sign-in CTA: “Sign in to save scheduling and progress”

### 3. Interval review подается как тест на правильность, а не как оценка качества воспоминания

Сейчас в interval mode:

- `again` и `hard` попадают в `incorrect`
- `good` и `easy` попадают в `correct`
- completion screen показывает:
  - `Accuracy`
  - `mastered`
  - `need review`

Это конфликтует с логикой spaced repetition.

Проблема:

- `Hard` не равен “неправильно”
- recall quality не равна exam correctness
- пользователь получает метрику, которая плохо отражает смысл SRS

UX-эффект:

- рождается ложная бинарная модель “правильно/неправильно”
- `Hard` психологически становится наказанием
- пользователь может начать переоценивать recall и жать `Good`, чтобы не портить accuracy

Frontend:

- `frontend/pages/study/study-actions.js:192`
- `frontend/pages/study/study-actions.js:196`
- `frontend/pages/study/study-render.js:195`
- `frontend/pages/study/study-viewer.js:168`

Recommendation:

- для interval mode заменить `Correct / Incorrect / Accuracy` на:
  - `Again`
  - `Hard`
  - `Good`
  - `Easy`
  - `Due left`
  - `Repeated today`
- completion screen должен объяснять scheduling outcome, а не “оценку”

## Medium

### 4. Пользователю не объясняют смысл кнопок Again / Hard / Good / Easy

Есть только общая фраза:

- `Rate quality to schedule the next appearance.`

Но нет operational guidance:

- когда жать `Again`
- когда жать `Hard`
- чем `Good` отличается от `Easy`

Для людей, которые не жили внутри Anki-подобной модели, это высокий cognitive load.

UX-эффект:

- пользователь боится “сломать алгоритм”
- кнопки кажутся экспертными
- появляются случайные стратегии ответов

Код:

- `frontend/pages/study/study-controls.js:251`

Recommendation:

- добавить mini help / tooltip / bottom sheet:
  - `Again`: “Не вспомнил или вспомнил неверно”
  - `Hard`: “Вспомнил, но с заметным усилием”
  - `Good`: “Нормально вспомнил”
  - `Easy`: “Вспомнил мгновенно”

### 5. Состав due queue почти не объясняется

Перед interval session пользователь видит только общее число карточек.

Но для UX важнее видеть composition:

- сколько overdue review
- сколько relearning
- сколько learning
- сколько new cards попадет в сессию

Сейчас queue воспринимается как “черный ящик”.

Код:

- `frontend/pages/study/study-render.js:93`
- `frontend/pages/study/study-render.js:100`

Recommendation:

- на стартовой панели interval mode показывать queue breakdown
- рядом дать короткое объяснение, почему именно эти карточки попали в текущий run

### 6. Backend умеет `new_cards_limit`, но UI это не дает контролировать

Backend endpoint поддерживает:

- `limit`
- `new_cards_limit`
- `shuffle_cards`

Но UI для interval mode реально использует только:

- `shuffle_cards`

Это заметный UX-gap.

Пользователь не может контролировать баланс между:

- due reviews
- новыми карточками
- общим daily load

Код:

- `backend/deck_study_router.py:14`
- `frontend/pages/study/study-session.js:323`

Recommendation:

- добавить в interval settings:
  - `new cards per session`
  - возможно `max cards this run`

### 7. Interval start state для shared deck вводит в заблуждение словом “due”

Shared preview от backend возвращает все active cards без персонального scheduling state, но UI пишет:

- `X cards are currently available in the due queue`

Для гостя это неправда в терминах SRS: это не due queue, а список карточек deck preview.

Код:

- `frontend/pages/study/study-render.js:100`
- `backend/deck_share_router.py:26`

Recommendation:

- для shared/guest flow использовать другой copy:
  - `X cards available in preview`
  - `Sign in to unlock personal spaced repetition scheduling`

### 8. В deck interval overview показывается EF, но не объясняется его смысл

С точки зрения power-user это полезно.
С точки зрения большинства пользователей `EF` выглядит как внутренний технический жаргон.

UX-эффект:

- продвинутые пользователи получают пользу
- остальные видят загадочную колонку без смысла

Код:

- `frontend/pages/deck/deck-page.js:298`
- `frontend/pages/deck/deck-page.js:329`

Recommendation:

- либо добавить tooltip
- либо переименовать в `Ease`
- либо скрывать в compact mode и раскрывать по запросу

## Minor

### 9. Локализация и language model интерфейса несогласованы

На study page указан `html lang="ru"`, но почти весь UI-контент в interval flow написан по-английски.

UX-эффект:

- ощущение незавершенности продукта
- лишняя когнитивная нагрузка для русскоязычного пользователя
- потенциальные проблемы для screen readers и locale-specific formatting expectations

Код:

- `frontend/pages/study/index.html:2`
- `frontend/pages/study/index.html:30`
- `frontend/pages/study/study-page.js:57`
- `frontend/pages/deck/index.html:162`

Recommendation:

- либо сделать полноценный English UI и выровнять `lang`
- либо реально локализовать study/deck interval flows

### 10. Interval mode визуально силен, но не обучает

Визуально flow уже хороший, но он почти не помогает человеку стать “хорошим пользователем SRS”.

Система показывает:

- what to click

но слабо показывает:

- why this matters
- how the algorithm interprets the answer
- как выстроить правильную привычку

## UX Principles Check

### Principle 1: Trust

Сейчас нарушается в двух местах:

- preview на кнопках не всегда соответствует реальности
- guest interval mode выглядит сохраняемым, но не сохраняется

Вывод:

- trust level: medium-risk

### Principle 2: Clarity

Сильные стороны:

- flow reveal -> rate очень ясен
- deck interval list хорошо объясняет состояние карточки

Слабые стороны:

- слабое объяснение rating semantics
- queue composition непрозрачна
- completion language больше про “экзамен”, чем про scheduling

Вывод:

- clarity level: medium

### Principle 3: Learnability

Сильные стороны:

- кнопки и шорткаты быстро осваиваются

Слабые стороны:

- модель `Again / Hard / Good / Easy` не обучается интерфейсом
- пользователь сам конструирует правила использования

Вывод:

- learnability level: medium-low

### Principle 4: Feedback Quality

Сильные стороны:

- есть next interval preview
- есть due state и word list overview

Слабые стороны:

- preview logic desynced
- session summary metric не соответствует природе SRS

Вывод:

- feedback quality: medium-risk

## Priority Recommendations

## P0

### 1. Синхронизировать interval previews с backend scheduler-ом

Без этого нельзя считать interval UI trustworthy.

Лучший вариант:

- сервер возвращает preview map для текущей карточки и rating set

Альтернатива:

- shared scheduling module / strict contract-tests между JS и Python

### 2. Развести guest preview и real interval review

Нужно убрать ложное обещание персонального scheduling для гостей.

Варианты:

- скрыть interval mode для гостя
- показать read-only preview variant
- оставить UI, но добавить явный banner:
  - `Ratings are not saved in preview mode`
  - `Sign in to track intervals and progress`

### 3. Переписать session feedback language для interval mode

Нужно убрать test framing:

- `Accuracy`
- `Correct`
- `Incorrect`

И заменить на SRS framing:

- `Again / Hard / Good / Easy`
- `Cards repeated today`
- `Due queue cleared`
- `Returned to relearning`

## P1

### 4. Добавить microcopy с объяснением rating buttons

Минимальный вариант:

- tooltip / help link рядом с rating row

Лучший вариант:

- first-run coach mark
- persistent “How ratings work” panel in settings/help

### 5. Показать queue composition перед стартом interval session

Например:

- `Due now: 12`
- `Learning: 3`
- `Relearning: 2`
- `New today: 5`

### 6. Добавить контроль `new_cards_limit` в UI

Это резко повысит чувство контроля над daily load.

## P2

### 7. Объяснить `Ease / EF` в deck interval overview

### 8. Выровнять локализацию и copywriting

### 9. Улучшить completion summary именно для interval mode

Например:

- `You cleared 18 due cards`
- `4 cards came back for another pass`
- `2 cards moved into relearning`
- `Most ratings were Good`

## Suggested Future Research

Чтобы превратить этот audit в настоящее UX research, следующими шагами я бы рекомендовал:

1. 5 moderated usability sessions по interval mode
2. event tracking на:
   - first interval session start
   - reveal answer
   - rating distribution
   - abort points
   - guest vs signed-in conversion
3. анализ:
   - как часто жмут `Hard`
   - насколько перекошен usage между `Good` и `Easy`
   - есть ли drop-off после первого interval experience
4. короткий survey после session completion:
   - “Понимаете ли вы разницу между Hard и Good?”
   - “Доверяете ли вы подсказке следующего интервала?”

## Final Assessment

С точки зрения UX это уже не “сырая система интервального повторения”.
У продукта уже есть хороший каркас:

- заметный interval mode
- прозрачность состояний карточек
- отдельный word list overview
- focus interaction
- keyboard-first flow

Но до действительно сильного SRS UX не хватает трех вещей:

1. честности интерфейса относительно того, что реально делает алгоритм
2. более точной product language для recall quality вместо test accuracy
3. более понятного onboarding в саму модель spaced repetition

Итоговая оценка:

- Scheduler UX foundation: strong
- Trust in interval controls: needs urgent improvement
- Guest/shared interval UX: misleading
- Education/onboarding around SRS model: underdesigned
- Overall maturity: good base, not yet polished enough for full user trust
