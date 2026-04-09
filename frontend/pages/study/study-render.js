window.studyRender = (() => {
  function createStudyRenderer(ctx) {
    const { state, dom, helpers, actions, accountMenuUi, config } = ctx;
    const {
      modeGrid,
      setupPanel,
      deckTitle,
      deckSubtitle,
      deckOwnerLabel,
      readOnlyBadge,
      savedDeckBadge,
      privacyBadge,
      shareAccessHint,
      cloneDeckBtn,
      editDeckBtn,
      groupsBtn,
      openEditorMenuBtn,
      statsGrid,
      cardViewer,
      controlBar,
    } = dom;
    const {
      MODES,
      escapeHtml,
      sharedApi,
      isSessionCompleted,
      isSessionActive,
      currentCard,
      primaryCardSide,
      secondaryCardSide,
      currentSideLabel,
      isPersistentIntervalSession,
      isPreviewIntervalSession,
      getIntervalQueueCards,
      buildIntervalQueueBreakdown,
      countIntervalRepetitions,
      canUndoSessionAction,
      shuffle,
      api,
      syncFlipPresentation,
      captureSessionSnapshot,
      pushSessionUndo,
    } = helpers;
    const {
      loadDeck,
      toggleFocusMode,
      undoLastSessionAction,
      saveStudySettings,
      startCurrentSessionWithSettings,
    } = actions;
    const { deckId } = config;

    function renderAll() {
      return actions.renderAll?.();
    }

    function renderProfile() {
      accountMenuUi.render(state.me);
    }

    function intervalModeMeta() {
      const previewOnly = Boolean(state.dueSession && !isPersistentIntervalSession());
      return previewOnly
        ? {
            label: "Предпросмотр интервалов",
            copy: state.me
              ? "Попробуйте интервальные оценки. Сохраните колоду, чтобы отслеживать персональное расписание."
              : "Попробуйте интервальные оценки. Войдите и сохраните колоду, чтобы отслеживать прогресс.",
          }
        : {
            label: "Интервальное повторение",
            copy: "Карточки к повторению с кнопками интервальной оценки.",
          };
    }

    function formatIntervalQueueChips(breakdown) {
      return [
        breakdown.reviewCards ? { label: "К повторению", value: breakdown.reviewCards } : null,
        breakdown.overdueCards ? { label: "Просрочено", value: breakdown.overdueCards } : null,
        breakdown.learningCards ? { label: "Изучение", value: breakdown.learningCards } : null,
        breakdown.relearningCards ? { label: "Переизучение", value: breakdown.relearningCards } : null,
        breakdown.newCards ? { label: "Новые", value: breakdown.newCards } : null,
      ].filter(Boolean);
    }

    function renderModes() {
      const intervalMeta = intervalModeMeta();
      const modes = MODES.map((mode) => (
        mode.id === "interval" ? { ...mode, label: intervalMeta.label, copy: intervalMeta.copy } : mode
      ));
      modeGrid.innerHTML = modes.map((mode) => `
        <div class="col-12 col-xl-4">
          <button class="card mode-tile w-100 h-100 text-start shadow-sm rounded-4 ${state.mode === mode.id ? "active" : ""}" type="button" data-mode="${mode.id}">
            <div class="card-body d-grid gap-3">
              <div class="d-flex align-items-center justify-content-between gap-2">
                <span class="mode-icon"><i class="bi ${mode.icon}"></i></span>
                ${state.mode === mode.id ? '<span class="mode-current">Текущий</span>' : ""}
              </div>
              <div>
                <div class="mode-title">${mode.label}</div>
                <div class="mode-copy">${mode.copy}</div>
              </div>
            </div>
          </button>
        </div>
      `).join("");
    }

    function renderSetup() {
      if (state.mode === "limit" && !state.started) {
        setupPanel.classList.remove("d-none");
        setupPanel.innerHTML = `
          <div class="card-body d-grid gap-3">
            <div>
              <strong class="d-block mb-1">Повторить фиксированное число карточек</strong>
              <div class="text-secondary">Выберите размер сессии перед стартом.</div>
            </div>
            <div class="d-flex gap-2 flex-wrap">
              ${[10, 20, 30, "all"].map((value) => `<button class="btn ${String(state.sessionLimit) === String(value) ? "btn-light text-dark" : "btn-outline-light"} rounded-pill" type="button" data-limit="${value}">${value === "all" ? "Все" : value}</button>`).join("")}
              <button class="btn ${state.shuffleCards ? "btn-light text-dark" : "btn-outline-light"} rounded-pill" type="button" id="randomToggleBtn">Случайный порядок</button>
              <button class="btn btn-light text-dark" type="button" id="startLimitBtn">Начать сессию</button>
            </div>
          </div>
        `;
        return;
      }
      if (state.mode === "interval" && !state.started) {
        const queueCards = getIntervalQueueCards();
        const breakdown = buildIntervalQueueBreakdown(queueCards);
        const intervalMeta = intervalModeMeta();
        const previewOnly = isPreviewIntervalSession();
        const resumeSession = (state.dueSession?.current_index || 0) > 0;
        const queueChips = formatIntervalQueueChips(breakdown);
        const startLabel = previewOnly
          ? (resumeSession ? "Продолжить предпросмотр" : "Начать предпросмотр")
          : (resumeSession ? "Продолжить интервальное повторение" : "Начать интервальное повторение");
        const ctaLabel = state.me ? "Сохранить в мои колоды" : "Войти и сохранить прогресс";
        setupPanel.classList.remove("d-none");
        setupPanel.innerHTML = `
          <div class="card-body d-grid gap-3">
            <div class="d-grid gap-2">
              <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <strong class="d-block mb-0">Очередь: ${intervalMeta.label}</strong>
                ${previewOnly ? '<span class="badge rounded-pill text-bg-warning text-dark">Только предпросмотр</span>' : ""}
              </div>
              <div class="text-secondary">
                ${previewOnly
                  ? `В предпросмотре доступно ${breakdown.total} карточек. Оценки не сохраняются и не меняют персональное расписание.`
                  : `Сейчас в очереди к повторению доступно ${breakdown.total} карточек.`}
              </div>
              ${queueChips.length ? `
                <div class="interval-breakdown-row">
                  ${queueChips.map((item) => `
                    <span class="interval-breakdown-chip">
                      <span>${escapeHtml(item.label)}</span>
                      <strong>${escapeHtml(String(item.value))}</strong>
                    </span>
                  `).join("")}
                </div>
              ` : ""}
              <div class="small text-secondary">
                ${previewOnly
                  ? (state.me
                    ? "Сохраните эту колоду в библиотеку, чтобы включить персональное интервальное расписание."
                    : "Войдите и сохраните эту колоду, чтобы включить персональное интервальное расписание.")
                  : "Очередь включает карточки в изучении, переизучении и запланированные повторы для этой сессии."}
              </div>
            </div>
            <div class="d-flex gap-2 flex-wrap align-items-center">
              <button class="btn btn-light text-dark" type="button" id="startIntervalBtn">${startLabel}</button>
              ${previewOnly ? `<button class="btn btn-outline-light" type="button" id="intervalSaveProgressBtn">${ctaLabel}</button>` : ""}
            </div>
          </div>
        `;
        return;
      }
      setupPanel.classList.add("d-none");
      setupPanel.innerHTML = "";
    }

    function modeLabel() {
      if (state.mode === "interval") return intervalModeMeta().label;
      return MODES.find((mode) => mode.id === state.mode)?.label || "Центр колоды";
    }

    function currentDeckLink() {
      return `${window.location.origin}/study?deck=${deckId}`;
    }

    function currentOwnerName() {
      return state.deck?.owner_name || state.sharedMeta?.owner_name || "Неизвестный автор";
    }

    function renderPrivacyState() {
      const visibility = state.deck?.visibility || state.sharedMeta?.visibility || "private";
      const isPrivate = visibility === "private";
      deckOwnerLabel.textContent = `Автор: ${currentOwnerName()}`;
      readOnlyBadge.classList.toggle("d-none", state.ownerAccess || !state.deck);
      savedDeckBadge.classList.toggle("d-none", !state.deck?.saved_in_library || state.ownerAccess);
      privacyBadge.textContent = isPrivate ? "Приватная" : "Публичная";
      privacyBadge.className = `badge rounded-pill ${isPrivate ? "text-bg-warning text-dark" : "text-bg-success"}`;
      shareAccessHint.textContent = isPrivate
        ? "Ссылка защищена паролем. Для просмотра нужен пароль колоды."
        : "Открытая ссылка. Любой, у кого есть URL, может просматривать эту колоду.";
      cloneDeckBtn.classList.toggle("d-none", Boolean(state.ownerAccess) || !state.deck || Boolean(state.deck?.saved_in_library));
      editDeckBtn.classList.remove("d-none");
      groupsBtn.classList.toggle("d-none", !state.ownerAccess);
      openEditorMenuBtn.classList.remove("d-none");
    }

    function renderHeader() {
      if (!state.deck) {
        deckTitle.textContent = "Колода не найдена";
        deckSubtitle.textContent = "Выберите корректную колоду с главной страницы.";
        renderPrivacyState();
        return;
      }
      deckTitle.textContent = state.deck.name;
      if (!state.started) {
        deckSubtitle.textContent = `Выбран режим «${modeLabel()}». Настройте его и начните сессию.`;
      } else if (isSessionCompleted()) {
        deckSubtitle.textContent = `Режим «${modeLabel()}» завершён. Ниже уже готова сводка по сессии.`;
      } else {
        const activeStep = Math.min(state.currentIndex + 1, Math.max(state.sessionCards.length, 1));
        deckSubtitle.textContent = `Режим «${modeLabel()}» в процессе: карточка ${activeStep} из ${state.sessionCards.length}.`;
      }
      editDeckBtn.href = `/deck?id=${state.deck.id}&view=interval`;
      editDeckBtn.innerHTML = '<i class="bi bi-list-ul me-2"></i>Список слов';
      renderPrivacyState();
    }

    function renderStats() {
      const total = state.sessionCards.length;
      const intervalStartIndex = state.intervalStartIndex || 0;
      const intervalTotal = state.mode === "interval" ? Math.max(total - intervalStartIndex, 0) : total;
      const intervalRatings = state.intervalRatings || { again: 0, hard: 0, good: 0, easy: 0 };
      const intervalReviewed = state.mode === "interval"
        ? Math.max(Math.min(state.currentIndex, total) - intervalStartIndex, 0)
        : intervalRatings.again + intervalRatings.hard + intervalRatings.good + intervalRatings.easy;
      const reviewed = state.mode === "interval"
        ? Math.min(intervalReviewed, intervalTotal)
        : Math.min(state.correct + state.incorrect, total);
      const completion = (state.mode === "interval" ? intervalTotal : total)
        ? Math.round((reviewed / (state.mode === "interval" ? intervalTotal : total)) * 100)
        : 0;
      const remaining = Math.max((state.mode === "interval" ? intervalTotal : total) - reviewed, 0);
      const completedSession = isSessionCompleted();
      const repeatedToday = countIntervalRepetitions(state.sessionCards.slice(intervalStartIndex));

      statsGrid.classList.toggle("is-completed", completedSession);

      if (state.mode === "interval" && !state.started) {
        const breakdown = buildIntervalQueueBreakdown(getIntervalQueueCards());
        const queueStats = [
          {
            label: "Карточек в очереди",
            value: String(breakdown.total),
            note: isPreviewIntervalSession() ? "Карточки для предпросмотра" : "Готово для этой сессии",
            className: "stat-primary",
          },
          {
            label: "К повторению",
            value: String(breakdown.reviewCards),
            note: breakdown.overdueCards ? `${breakdown.overdueCards} просрочено` : "Запланированные повторы",
            className: "stat-positive",
          },
          {
            label: "Изучение",
            value: String(breakdown.learningCards + breakdown.relearningCards),
            note: breakdown.relearningCards ? `${breakdown.relearningCards} в переизучении` : "Изучение и переизучение",
            className: "stat-negative",
          },
          {
            label: "Новые карточки",
            value: String(breakdown.newCards),
            note: isPreviewIntervalSession() ? "Карточки колоды в предпросмотре" : `Максимум ${state.newCardsLimit} за сессию`,
            className: "stat-muted",
          },
        ];
        statsGrid.innerHTML = queueStats.map((item) => `
          <div class="col-12 col-md-6 col-xxl-3">
            <div class="card stat-card shadow-sm rounded-4 h-100 ${item.className}">
              <div class="card-body">
                <div class="stat-label">${item.label}</div>
                <div class="stat-value">${item.value}</div>
                <div class="stat-note">${item.note}</div>
              </div>
            </div>
          </div>
        `).join("");
        return;
      }

      if (state.mode === "interval" && completedSession) {
        const progressNote = repeatedToday
          ? `${repeatedToday} карточек вернулось на дополнительный проход в этой сессии.`
          : "Очередь к повторению в этой сессии очищена.";
        statsGrid.innerHTML = `
          <div class="col-12">
            <div class="card stat-card completion-metrics-strip rounded-4 h-100">
              <div class="card-body">
                <div class="completion-progress-main">
                  <div class="label">Сводка по интервалам</div>
                  <div class="value">${reviewed} / ${intervalTotal}</div>
                  <div class="note">${progressNote}</div>
                </div>
                <div class="completion-inline-metrics">
                  <span class="completion-chip interval-again"><span>Снова</span><strong>${intervalRatings.again}</strong></span>
                  <span class="completion-chip interval-hard"><span>Трудно</span><strong>${intervalRatings.hard}</strong></span>
                  <span class="completion-chip interval-good"><span>Хорошо</span><strong>${intervalRatings.good}</strong></span>
                  <span class="completion-chip interval-easy"><span>Легко</span><strong>${intervalRatings.easy}</strong></span>
                  <span class="completion-chip remaining ${repeatedToday === 0 ? "zero" : ""}"><span>Повторилось сегодня</span><strong>${repeatedToday}</strong></span>
                </div>
              </div>
            </div>
          </div>
        `;
        return;
      }

      if (completedSession) {
        const progressNote = remaining === 0
          ? "Все карточки просмотрены в этой сессии."
          : `Осталось ${remaining} карточек в этой сессии.`;
        statsGrid.innerHTML = `
          <div class="col-12">
            <div class="card stat-card completion-metrics-strip rounded-4 h-100">
              <div class="card-body">
                <div class="completion-progress-main">
                  <div class="label">Прогресс сессии</div>
                  <div class="value">${reviewed} / ${total}</div>
                  <div class="note">${progressNote}</div>
                </div>
                <div class="completion-inline-metrics">
                  <span class="completion-chip correct"><span>Верно</span><strong>${state.correct}</strong></span>
                  <span class="completion-chip incorrect"><span>Неверно</span><strong>${state.incorrect}</strong></span>
                  <span class="completion-chip remaining ${remaining === 0 ? "zero" : ""}"><span>Осталось</span><strong>${remaining}</strong></span>
                </div>
              </div>
            </div>
          </div>
        `;
        return;
      }

      if (state.mode === "interval") {
        const stats = [
          {
            label: "Прогресс сессии",
            value: intervalTotal ? `${reviewed} / ${intervalTotal}` : "0 / 0",
            note: intervalTotal ? `${completion}% завершено` : "Нет активных карточек",
            className: "stat-primary",
          },
          {
            label: "Снова",
            value: String(intervalRatings.again),
            note: "Забыли или не вспомнили",
            className: "stat-negative",
          },
          {
            label: "Трудно",
            value: String(intervalRatings.hard),
            note: "Вспомнили с усилием",
            className: "stat-negative",
          },
          {
            label: "Хорошо",
            value: String(intervalRatings.good),
            note: "Обычное вспоминание",
            className: "stat-positive",
          },
          {
            label: "Легко",
            value: String(intervalRatings.easy),
            note: "Мгновенное вспоминание",
            className: "stat-positive",
          },
          {
            label: "Повторилось сегодня",
            value: String(repeatedToday),
            note: "Карточки, вернувшиеся в этой сессии",
            className: "stat-muted",
          },
        ];
        statsGrid.innerHTML = stats.map((item) => `
          <div class="col-12 col-md-6 col-xxl-3">
            <div class="card stat-card shadow-sm rounded-4 h-100 ${item.className}">
              <div class="card-body">
                <div class="stat-label">${item.label}</div>
                <div class="stat-value">${item.value}</div>
                <div class="stat-note">${item.note}</div>
              </div>
            </div>
          </div>
        `).join("");
        return;
      }

      const stats = [
        {
          label: "Прогресс сессии",
          value: total ? `${reviewed} / ${total}` : "0 / 0",
          note: total ? `${completion}% завершено` : "Нет активных карточек",
          className: "stat-primary",
        },
        {
          label: "Верно",
          value: String(state.correct),
          note: "Известные карточки",
          className: "stat-positive",
        },
        {
          label: "Неверно",
          value: String(state.incorrect),
          note: "Нужно повторить",
          className: "stat-negative",
        },
        {
          label: "Осталось",
          value: String(remaining),
          note: "Карточек осталось",
          className: "stat-muted",
        },
      ];
      statsGrid.innerHTML = stats.map((item) => `
        <div class="col-12 col-md-6 col-xxl-3">
          <div class="card stat-card shadow-sm rounded-4 h-100 ${item.className}">
            <div class="card-body">
              <div class="stat-label">${item.label}</div>
              <div class="stat-value">${item.value}</div>
              <div class="stat-note">${item.note}</div>
            </div>
          </div>
        </div>
      `).join("");
    }

    const actionApi = window.studyActions.createStudyActions({
      state,
      helpers: {
        api,
        currentCard,
        shuffle,
        syncFlipPresentation,
        captureSessionSnapshot,
        pushSessionUndo,
      },
      actions: {
        renderAll,
        renderControls: () => controlApi.renderControls(),
      },
    });

    const viewerApi = window.studyViewer.createStudyViewer({
      state,
      dom: { cardViewer, controlBar },
      helpers: {
        escapeHtml,
        sharedApi,
        isSessionCompleted,
        currentCard,
        primaryCardSide,
        secondaryCardSide,
        currentSideLabel,
        isPreviewIntervalSession,
        countIntervalRepetitions,
        canUndoSessionAction,
      },
      actions: {
        loadDeck,
        undoLastSessionAction,
        startMode: actionApi.startMode,
        beginPreparedSession: actionApi.beginPreparedSession,
        buildTestChoices: actionApi.buildTestChoices,
        answerTest: actionApi.answerTest,
        flipCurrentCard: actionApi.flipCurrentCard,
        modeLabel,
        startCurrentSessionWithSettings,
        renderAll,
      },
      config: { deckId },
    });

    const controlApi = window.studyControls.createStudyControls({
      state,
      dom: { controlBar },
      helpers: {
        isSessionActive,
        canUndoSessionAction,
        primaryCardSide,
        currentCard,
        buildIntervalRatingPreviews: helpers.buildIntervalRatingPreviews,
        isPreviewIntervalSession,
        captureSessionSnapshot,
        pushSessionUndo,
      },
      actions: {
        toggleFocusMode,
        completeSelfCheck: actionApi.completeSelfCheck,
        beginPreparedSession: actionApi.beginPreparedSession,
        flipCurrentCard: actionApi.flipCurrentCard,
        submitIntervalRating: actionApi.submitIntervalRating,
        nextTestCard: actionApi.nextTestCard,
        undoLastSessionAction,
        saveStudySettings,
        startCurrentSessionWithSettings,
        renderViewer: viewerApi.renderViewer,
      },
    });

    return {
      renderProfile,
      renderModes,
      renderSetup,
      modeLabel,
      currentDeckLink,
      renderPrivacyState,
      renderHeader,
      renderStats,
      ...actionApi,
      ...viewerApi,
      ...controlApi,
    };
  }

  return { createStudyRenderer };
})();
