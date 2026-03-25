window.studySession = (() => {
  function createStudySession(ctx) {
    const { state, dom, helpers, config, actions } = ctx;
    const { focusTopbar, focusProgressPill, focusDeckTitleLabel, focusModeChip, cardViewer } = dom;
    const { api, sharedApi } = helpers;
    const { DEFAULT_STUDY_SETTINGS, deckId } = config;

    function renderAll() {
      return actions.renderAll?.();
    }

    function renderControls() {
      return actions.renderControls?.();
    }

    function startMode(modeId) {
      return actions.startMode?.(modeId);
    }

    function modeLabel() {
      return actions.modeLabel?.() || "Deck Hub";
    }

    function normalizeStudySettings(raw = {}) {
      return {
        cardSideOrder: raw.cardSideOrder === "back" ? "back" : DEFAULT_STUDY_SETTINGS.cardSideOrder,
        shuffleCards: Boolean(raw.shuffleCards),
      };
    }

    function studySettingsDeckScope() {
      return deckId ? `deck:${deckId}` : "deck:default";
    }

    function studySettingsStorageKey() {
      const scope = studySettingsDeckScope();
      return state.me ? `deckly:study-settings:user:${state.me.id}:${scope}` : `deckly:study-settings:guest:${scope}`;
    }

    function saveStudySettings() {
      const payload = JSON.stringify(
        normalizeStudySettings({
          cardSideOrder: state.cardSideOrder,
          shuffleCards: state.shuffleCards,
        })
      );
      localStorage.setItem(studySettingsStorageKey(), payload);
    }

    function loadStudySettings() {
      const stored = localStorage.getItem(studySettingsStorageKey());
      if (!stored) {
        state.cardSideOrder = DEFAULT_STUDY_SETTINGS.cardSideOrder;
        state.shuffleCards = DEFAULT_STUDY_SETTINGS.shuffleCards;
        return;
      }
      try {
        const parsed = JSON.parse(stored);
        const normalized = normalizeStudySettings(parsed);
        state.cardSideOrder = normalized.cardSideOrder;
        state.shuffleCards = normalized.shuffleCards;
      } catch (error) {
        state.cardSideOrder = DEFAULT_STUDY_SETTINGS.cardSideOrder;
        state.shuffleCards = DEFAULT_STUDY_SETTINGS.shuffleCards;
      }
    }

    function shuffle(array) {
      const items = [...array];
      for (let i = items.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [items[i], items[j]] = [items[j], items[i]];
      }
      return items;
    }

    function clampIndex() {
      if (!state.sessionCards.length) {
        state.currentIndex = 0;
        return;
      }
      state.currentIndex = Math.max(0, Math.min(state.currentIndex, state.sessionCards.length - 1));
    }

    function currentCard() {
      clampIndex();
      return state.sessionCards[state.currentIndex] || null;
    }

    function captureSessionSnapshot() {
      return {
        currentIndex: state.currentIndex,
        revealed: state.revealed,
        correct: state.correct,
        incorrect: state.incorrect,
        missedCardIds: [...state.missedCardIds],
        lastAnswer: state.lastAnswer ? { ...state.lastAnswer } : null,
        testChoices: [...state.testChoices]
      };
    }

    function pushSessionUndo(snapshot) {
      state.actionHistory.push(snapshot);
      if (state.actionHistory.length > 80) state.actionHistory.shift();
    }

    function canUndoSessionAction() {
      return Boolean(state.actionHistory.length && state.started && state.sessionCards.length);
    }

    function undoLastSessionAction() {
      const snapshot = state.actionHistory.pop();
      if (!snapshot) return;
      state.currentIndex = snapshot.currentIndex;
      state.revealed = snapshot.revealed;
      state.correct = snapshot.correct;
      state.incorrect = snapshot.incorrect;
      state.missedCardIds = [...snapshot.missedCardIds];
      state.lastAnswer = snapshot.lastAnswer ? { ...snapshot.lastAnswer } : null;
      state.testChoices = [...snapshot.testChoices];
      renderAll();
    }

    function isSessionActive() {
      return Boolean(state.started && state.sessionCards.length && state.currentIndex < state.sessionCards.length);
    }

    function isSessionCompleted() {
      return Boolean(state.started && state.sessionCards.length && state.currentIndex >= state.sessionCards.length);
    }

    function syncFocusQueryParam(enabled) {
      const url = new URL(window.location.href);
      if (enabled) url.searchParams.set("focus", "1");
      else url.searchParams.delete("focus");
      window.history.replaceState({}, "", url.toString());
    }

    function syncFocusTopbar() {
      if (!focusTopbar) return;
      const total = state.sessionCards.length;
      const current = Math.min(state.currentIndex + 1, Math.max(total, 1));
      const progressText = isSessionCompleted()
        ? `Complete · ${total} / ${total}`
        : `${current} / ${total || 0}`;
      if (focusProgressPill) focusProgressPill.textContent = progressText;
      if (focusDeckTitleLabel) {
        const name = state.deck?.name || state.sharedMeta?.name || "Study session";
        focusDeckTitleLabel.textContent = name;
        focusDeckTitleLabel.title = name;
      }
      if (focusModeChip) focusModeChip.textContent = modeLabel();
    }

    function syncFocusModeLayout() {
      const canFocus = isSessionActive() || isSessionCompleted();
      if (!canFocus && state.focusMode) state.focusMode = false;
      const enabled = Boolean(state.focusMode && canFocus);
      document.body.classList.toggle("study-focus-mode", enabled);
      document.body.classList.toggle("study-focus-lock", enabled);
      document.documentElement.classList.toggle("study-focus-lock", enabled);
      if (focusTopbar) focusTopbar.classList.toggle("d-none", !enabled);
      if (enabled) syncFocusTopbar();
      if (!enabled && document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      syncFocusQueryParam(enabled);
    }

    function syncStudyFocusLayout() {
      document.body.classList.toggle("study-active", isSessionActive());
      syncFocusModeLayout();
    }

    async function toggleFocusMode(forceValue = null) {
      if (!isSessionActive() && !isSessionCompleted()) return;
      const nextValue = typeof forceValue === "boolean" ? forceValue : !state.focusMode;
      state.focusMode = nextValue;
      state.settingsOpen = false;
      syncStudyFocusLayout();
      renderControls();
      try {
        if (nextValue && document.documentElement.requestFullscreen && !document.fullscreenElement) {
          await document.documentElement.requestFullscreen();
        } else if (!nextValue && document.exitFullscreen && document.fullscreenElement) {
          await document.exitFullscreen();
        }
      } catch (error) {
        // Focus mode still works without native fullscreen permissions.
      }
    }

    function primaryCardSide() {
      return state.cardSideOrder === 'back' ? 'back' : 'front';
    }

    function secondaryCardSide() {
      return primaryCardSide() === 'front' ? 'back' : 'front';
    }

    function currentSideLabel(revealed) {
      return (revealed ? secondaryCardSide() : primaryCardSide()) === 'front' ? 'Front' : 'Back';
    }

    async function loadIntervalSession() {
      if (!deckId) return null;
      if (state.me) {
        const params = new URLSearchParams({
          mode: "interval",
          shuffle_cards: state.shuffleCards ? "true" : "false"
        });
        state.dueSession = await api(`/decks/${deckId}/study/session?${params.toString()}`);
        return state.dueSession;
      }
      state.dueSession = await sharedApi(`/shared/decks/${deckId}/study`);
      return state.dueSession;
    }

    async function startCurrentSessionWithSettings() {
      if (!state.mode) return;
      state.settingsOpen = false;
      if (state.mode === 'interval') {
        await loadIntervalSession();
      }
      startMode(state.mode);
    }

    function syncFlipPresentation() {
      const flipSurface = cardViewer.querySelector('[data-flip-card]');
      const stateBadge = document.getElementById('reviewStateBadge');

      if (flipSurface) {
        flipSurface.classList.toggle('is-flipped', state.revealed);
      }

      if (stateBadge) {
        stateBadge.textContent = currentSideLabel(state.revealed);
        stateBadge.className = `badge ${state.revealed ? 'text-bg-success' : 'text-bg-secondary'} rounded-pill`;
      }
    }


    return {
      saveStudySettings,
      loadStudySettings,
      shuffle,
      currentCard,
      captureSessionSnapshot,
      pushSessionUndo,
      canUndoSessionAction,
      undoLastSessionAction,
      isSessionActive,
      isSessionCompleted,
      syncStudyFocusLayout,
      toggleFocusMode,
      primaryCardSide,
      secondaryCardSide,
      currentSideLabel,
      loadIntervalSession,
      startCurrentSessionWithSettings,
      syncFlipPresentation,
    };
  }

  return { createStudySession };
})();
