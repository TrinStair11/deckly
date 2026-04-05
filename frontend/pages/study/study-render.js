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
            label: "Interval Preview",
            copy: state.me
              ? "Preview spaced repetition ratings. Save this deck to track personal scheduling."
              : "Preview spaced repetition ratings. Sign in and save the deck to track progress.",
          }
        : {
            label: "Interval Review",
            copy: "Due cards with spaced repetition rating buttons.",
          };
    }

    function formatIntervalQueueChips(breakdown) {
      return [
        breakdown.reviewCards ? { label: "Due Reviews", value: breakdown.reviewCards } : null,
        breakdown.overdueCards ? { label: "Overdue", value: breakdown.overdueCards } : null,
        breakdown.learningCards ? { label: "Learning", value: breakdown.learningCards } : null,
        breakdown.relearningCards ? { label: "Relearning", value: breakdown.relearningCards } : null,
        breakdown.newCards ? { label: "New", value: breakdown.newCards } : null,
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
                ${state.mode === mode.id ? '<span class="mode-current">Current</span>' : ""}
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
              <strong class="d-block mb-1">Review a fixed number of cards</strong>
              <div class="text-secondary">Choose the session size before you start.</div>
            </div>
            <div class="d-flex gap-2 flex-wrap">
              ${[10, 20, 30, "all"].map((value) => `<button class="btn ${String(state.sessionLimit) === String(value) ? "btn-light text-dark" : "btn-outline-light"} rounded-pill" type="button" data-limit="${value}">${value === "all" ? "All" : value}</button>`).join("")}
              <button class="btn ${state.shuffleCards ? "btn-light text-dark" : "btn-outline-light"} rounded-pill" type="button" id="randomToggleBtn">Random Order</button>
              <button class="btn btn-light text-dark" type="button" id="startLimitBtn">Start Session</button>
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
          ? (resumeSession ? "Resume Preview" : "Start Preview")
          : (resumeSession ? "Resume Interval Review" : "Start Interval Review");
        const ctaLabel = state.me ? "Save to My Decks" : "Sign In to Save Progress";
        setupPanel.classList.remove("d-none");
        setupPanel.innerHTML = `
          <div class="card-body d-grid gap-3">
            <div class="d-grid gap-2">
              <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <strong class="d-block mb-0">${intervalMeta.label} Queue</strong>
                ${previewOnly ? '<span class="badge rounded-pill text-bg-warning text-dark">Preview only</span>' : ""}
              </div>
              <div class="text-secondary">
                ${previewOnly
                  ? `${breakdown.total} cards are available in preview. Ratings are not saved and this run does not update a personal schedule.`
                  : `${breakdown.total} cards are currently available in the due queue.`}
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
                    ? "Save this deck to your library to unlock personal spaced repetition scheduling."
                    : "Sign in and save this deck to unlock personal spaced repetition scheduling.")
                  : "Queue includes due learning and relearning cards plus scheduled reviews for this run."}
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
      return MODES.find((mode) => mode.id === state.mode)?.label || "Deck Hub";
    }

    function currentDeckLink() {
      return `${window.location.origin}/study?deck=${deckId}`;
    }

    function currentOwnerName() {
      return state.deck?.owner_name || state.sharedMeta?.owner_name || "Unknown creator";
    }

    function renderPrivacyState() {
      const visibility = state.deck?.visibility || state.sharedMeta?.visibility || "private";
      const isPrivate = visibility === "private";
      deckOwnerLabel.textContent = `Created by ${currentOwnerName()}`;
      readOnlyBadge.classList.toggle("d-none", state.ownerAccess || !state.deck);
      savedDeckBadge.classList.toggle("d-none", !state.deck?.saved_in_library || state.ownerAccess);
      privacyBadge.textContent = isPrivate ? "Private" : "Public";
      privacyBadge.className = `badge rounded-pill ${isPrivate ? "text-bg-warning text-dark" : "text-bg-success"}`;
      shareAccessHint.textContent = isPrivate
        ? "Password-protected link. Viewers must enter the deck password."
        : "Open-access link. Anyone with the URL can view this deck.";
      cloneDeckBtn.classList.toggle("d-none", Boolean(state.ownerAccess) || !state.deck || Boolean(state.deck?.saved_in_library));
      editDeckBtn.classList.remove("d-none");
      groupsBtn.classList.toggle("d-none", !state.ownerAccess);
      openEditorMenuBtn.classList.remove("d-none");
    }

    function renderHeader() {
      if (!state.deck) {
        deckTitle.textContent = "Deck not found";
        deckSubtitle.textContent = "Select a valid deck from the home page.";
        renderPrivacyState();
        return;
      }
      deckTitle.textContent = state.deck.name;
      if (!state.started) {
        deckSubtitle.textContent = `${modeLabel()} is selected. Configure it and start the session.`;
      } else if (isSessionCompleted()) {
        deckSubtitle.textContent = `${modeLabel()} complete — session summary is ready below.`;
      } else {
        const activeStep = Math.min(state.currentIndex + 1, Math.max(state.sessionCards.length, 1));
        deckSubtitle.textContent = `${modeLabel()} in progress — card ${activeStep} of ${state.sessionCards.length}.`;
      }
      editDeckBtn.href = `/deck?id=${state.deck.id}&view=interval`;
      editDeckBtn.innerHTML = '<i class="bi bi-list-ul me-2"></i>Word List';
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
            label: "Cards in Queue",
            value: String(breakdown.total),
            note: isPreviewIntervalSession() ? "Preview cards ready now" : "Ready for this run",
            className: "stat-primary",
          },
          {
            label: "Due Reviews",
            value: String(breakdown.reviewCards),
            note: breakdown.overdueCards ? `${breakdown.overdueCards} overdue` : "Scheduled reviews",
            className: "stat-positive",
          },
          {
            label: "Learning",
            value: String(breakdown.learningCards + breakdown.relearningCards),
            note: breakdown.relearningCards ? `${breakdown.relearningCards} relearning` : "Learning and relearning",
            className: "stat-negative",
          },
          {
            label: "New Cards",
            value: String(breakdown.newCards),
            note: isPreviewIntervalSession() ? "Preview deck cards" : `${state.newCardsLimit} max per run`,
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
          ? `${repeatedToday} card${repeatedToday === 1 ? "" : "s"} came back for another pass in this run.`
          : "Due queue cleared in this run.";
        statsGrid.innerHTML = `
          <div class="col-12">
            <div class="card stat-card completion-metrics-strip rounded-4 h-100">
              <div class="card-body">
                <div class="completion-progress-main">
                  <div class="label">Interval Summary</div>
                  <div class="value">${reviewed} / ${intervalTotal}</div>
                  <div class="note">${progressNote}</div>
                </div>
                <div class="completion-inline-metrics">
                  <span class="completion-chip interval-again"><span>Again</span><strong>${intervalRatings.again}</strong></span>
                  <span class="completion-chip interval-hard"><span>Hard</span><strong>${intervalRatings.hard}</strong></span>
                  <span class="completion-chip interval-good"><span>Good</span><strong>${intervalRatings.good}</strong></span>
                  <span class="completion-chip interval-easy"><span>Easy</span><strong>${intervalRatings.easy}</strong></span>
                  <span class="completion-chip remaining ${repeatedToday === 0 ? "zero" : ""}"><span>Repeated Today</span><strong>${repeatedToday}</strong></span>
                </div>
              </div>
            </div>
          </div>
        `;
        return;
      }

      if (completedSession) {
        const progressNote = remaining === 0
          ? "All cards reviewed in this run."
          : `${remaining} cards left in this run.`;
        statsGrid.innerHTML = `
          <div class="col-12">
            <div class="card stat-card completion-metrics-strip rounded-4 h-100">
              <div class="card-body">
                <div class="completion-progress-main">
                  <div class="label">Session Progress</div>
                  <div class="value">${reviewed} / ${total}</div>
                  <div class="note">${progressNote}</div>
                </div>
                <div class="completion-inline-metrics">
                  <span class="completion-chip correct"><span>Correct</span><strong>${state.correct}</strong></span>
                  <span class="completion-chip incorrect"><span>Incorrect</span><strong>${state.incorrect}</strong></span>
                  <span class="completion-chip remaining ${remaining === 0 ? "zero" : ""}"><span>Remaining</span><strong>${remaining}</strong></span>
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
            label: "Session Progress",
            value: intervalTotal ? `${reviewed} / ${intervalTotal}` : "0 / 0",
            note: intervalTotal ? `${completion}% completed` : "No active cards",
            className: "stat-primary",
          },
          {
            label: "Again",
            value: String(intervalRatings.again),
            note: "Forgot or failed recall",
            className: "stat-negative",
          },
          {
            label: "Hard",
            value: String(intervalRatings.hard),
            note: "Remembered with effort",
            className: "stat-negative",
          },
          {
            label: "Good",
            value: String(intervalRatings.good),
            note: "Normal recall",
            className: "stat-positive",
          },
          {
            label: "Easy",
            value: String(intervalRatings.easy),
            note: "Instant recall",
            className: "stat-positive",
          },
          {
            label: "Repeated Today",
            value: String(repeatedToday),
            note: "Cards that came back in this run",
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
          label: "Session Progress",
          value: total ? `${reviewed} / ${total}` : "0 / 0",
          note: total ? `${completion}% completed` : "No active cards",
          className: "stat-primary",
        },
        {
          label: "Correct",
          value: String(state.correct),
          note: "Known cards",
          className: "stat-positive",
        },
        {
          label: "Incorrect",
          value: String(state.incorrect),
          note: "Needs review",
          className: "stat-negative",
        },
        {
          label: "Remaining",
          value: String(remaining),
          note: "Cards left",
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
