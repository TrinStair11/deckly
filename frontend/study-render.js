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

    function renderModes() {
      modeGrid.innerHTML = MODES.map((mode) => `
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
        const dueCount = state.dueSession?.cards?.length || 0;
        setupPanel.classList.remove("d-none");
        setupPanel.innerHTML = `
          <div class="card-body d-grid gap-3">
            <div>
              <strong class="d-block mb-1">Interval Review Queue</strong>
              <div class="text-secondary">${dueCount} cards are currently available in the due queue.</div>
            </div>
            <div><button class="btn btn-light text-dark" type="button" id="startIntervalBtn">Start Interval Review</button></div>
          </div>
        `;
        return;
      }
      setupPanel.classList.add("d-none");
      setupPanel.innerHTML = "";
    }

    function modeLabel() {
      return MODES.find((mode) => mode.id === state.mode)?.label || "Deck Hub";
    }

    function currentDeckLink() {
      return `${window.location.origin}/study.html?deck=${deckId}`;
    }

    function currentOwnerName() {
      return state.deck?.owner_name || state.sharedMeta?.owner_name || state.deck?.owner_email || state.sharedMeta?.owner_email || "Unknown creator";
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
      editDeckBtn.classList.toggle("d-none", !state.ownerAccess);
      groupsBtn.classList.toggle("d-none", !state.ownerAccess);
      openEditorMenuBtn.classList.toggle("d-none", !state.ownerAccess);
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
      editDeckBtn.href = `/deck.html?id=${state.deck.id}`;
      renderPrivacyState();
    }

    function renderStats() {
      const total = state.sessionCards.length;
      const reviewed = Math.min(state.correct + state.incorrect, total);
      const completion = total ? Math.round((reviewed / total) * 100) : 0;
      const remaining = Math.max(total - reviewed, 0);
      const completedSession = isSessionCompleted();

      statsGrid.classList.toggle("is-completed", completedSession);

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
        canUndoSessionAction,
      },
      actions: {
        loadDeck,
        undoLastSessionAction,
        startMode: actionApi.startMode,
        buildTestChoices: actionApi.buildTestChoices,
        answerTest: actionApi.answerTest,
        flipCurrentCard: actionApi.flipCurrentCard,
        modeLabel,
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
        captureSessionSnapshot,
        pushSessionUndo,
      },
      actions: {
        toggleFocusMode,
        completeSelfCheck: actionApi.completeSelfCheck,
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
      currentOwnerName,
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
