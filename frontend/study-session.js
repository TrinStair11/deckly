window.studySession = (() => {
  function createStudySession(ctx) {
    const { state, dom, helpers, config, actions } = ctx;
    const { focusTopbar, focusProgressPill, focusDeckTitleLabel, focusModeChip, cardViewer } = dom;
    const { api, sharedApi } = helpers;
    const { DEFAULT_STUDY_SETTINGS, deckId } = config;
    const SM2_MIN_EASE_FACTOR = 1.3;
    const SM2_MAX_EASE_FACTOR = 2.8;
    const INITIAL_EASE_FACTOR = 2.5;
    const LEARNING_STEPS_MS = [60_000, 10 * 60_000];
    const RELEARNING_STEPS_MS = [10 * 60_000];
    const FIRST_REVIEW_INTERVAL_DAYS = 1;
    const SECOND_REVIEW_INTERVAL_DAYS = 6;
    const RATING_QUALITY = { again: 1, hard: 3, good: 4, easy: 5 };

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

    function normalizeIntervalCardState(card) {
      const source = card?.state || {};
      return {
        status: source.status || "new",
        learning_step: Number.isFinite(source.learning_step) ? source.learning_step : 0,
        reps: Number.isFinite(source.reps) ? source.reps : 0,
        lapses: Number.isFinite(source.lapses) ? source.lapses : 0,
        ease_factor: Number.isFinite(source.ease_factor) ? source.ease_factor : null,
        difficulty: Number.isFinite(source.difficulty) ? source.difficulty : INITIAL_EASE_FACTOR,
        scheduled_days: Number.isFinite(source.scheduled_days) ? source.scheduled_days : 0,
        elapsed_days: Number.isFinite(source.elapsed_days) ? source.elapsed_days : 0,
        last_reviewed_at: source.last_reviewed_at || null,
      };
    }

    function normalizeEaseFactor(rawEaseFactor) {
      if (!Number.isFinite(rawEaseFactor)) {
        return INITIAL_EASE_FACTOR;
      }
      return Math.min(Math.max(rawEaseFactor, SM2_MIN_EASE_FACTOR), SM2_MAX_EASE_FACTOR);
    }

    function getEaseFactor(stateSnapshot) {
      if (Number.isFinite(stateSnapshot.ease_factor)) {
        return normalizeEaseFactor(stateSnapshot.ease_factor);
      }
      if (
        Number.isFinite(stateSnapshot.difficulty) &&
        stateSnapshot.difficulty >= SM2_MIN_EASE_FACTOR &&
        stateSnapshot.difficulty <= SM2_MAX_EASE_FACTOR
      ) {
        return normalizeEaseFactor(stateSnapshot.difficulty);
      }
      return INITIAL_EASE_FACTOR;
    }

    function nextEaseFactor(easeFactor, quality) {
      const adjusted = easeFactor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
      return normalizeEaseFactor(adjusted);
    }

    function getHardLearningDelayMs(steps, currentStep) {
      const currentDelay = steps[currentStep];
      if (currentStep + 1 < steps.length) {
        const nextDelay = steps[currentStep + 1];
        return currentDelay + (nextDelay - currentDelay) / 2;
      }
      return Math.round(currentDelay * 1.5);
    }

    function previewLearningDelay(stateSnapshot, rating) {
      const isRelearning = stateSnapshot.status === "relearning";
      const steps = isRelearning ? RELEARNING_STEPS_MS : LEARNING_STEPS_MS;
      const currentStep = Math.min(Math.max(stateSnapshot.learning_step || 0, 0), steps.length - 1);

      if (rating === "again") return steps[0];
      if (rating === "hard") return getHardLearningDelayMs(steps, currentStep);
      if (rating === "good") {
        if (currentStep >= steps.length - 1) return FIRST_REVIEW_INTERVAL_DAYS * 86400_000;
        return steps[currentStep + 1];
      }
      return FIRST_REVIEW_INTERVAL_DAYS * 86400_000;
    }

    function previewReviewDelay(stateSnapshot, rating) {
      const quality = RATING_QUALITY[rating];
      const currentEaseFactor = getEaseFactor(stateSnapshot);
      const scheduledDays = Math.max(stateSnapshot.scheduled_days || 0, 0);

      if (quality < 3) return RELEARNING_STEPS_MS[0];

      if ((stateSnapshot.reps || 0) <= 0) {
        return FIRST_REVIEW_INTERVAL_DAYS * 86400_000;
      }
      if (stateSnapshot.reps === 1) {
        return SECOND_REVIEW_INTERVAL_DAYS * 86400_000;
      }

      const nextEase = nextEaseFactor(currentEaseFactor, quality);
      const baseInterval = Math.max(scheduledDays, FIRST_REVIEW_INTERVAL_DAYS);
      return Math.ceil(baseInterval * nextEase) * 86400_000;
    }

    function formatDelayLabel(delayMs) {
      if (delayMs < 60_000) return "now";
      const totalMinutes = Math.round(delayMs / 60_000);
      if (totalMinutes < 60) return `in ${totalMinutes}m`;
      const totalHours = Math.round(delayMs / 3_600_000);
      if (totalHours < 48) return `in ${totalHours}h`;
      const totalDays = Math.round(delayMs / 86_400_000);
      if (totalDays < 30) return `in ${totalDays}d`;
      const totalMonths = Math.round(totalDays / 30);
      return `in ${totalMonths}mo`;
    }

    function buildIntervalRatingPreviews(card) {
      const stateSnapshot = normalizeIntervalCardState(card);
      const computeDelay = stateSnapshot.status === "review" ? previewReviewDelay : previewLearningDelay;

      return {
        again: formatDelayLabel(computeDelay(stateSnapshot, "again")),
        hard: formatDelayLabel(computeDelay(stateSnapshot, "hard")),
        good: formatDelayLabel(computeDelay(stateSnapshot, "good")),
        easy: formatDelayLabel(computeDelay(stateSnapshot, "easy")),
      };
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
      buildIntervalRatingPreviews,
      loadIntervalSession,
      startCurrentSessionWithSettings,
      syncFlipPresentation,
    };
  }

  return { createStudySession };
})();
