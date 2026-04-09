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
    const RELEARNING_STEPS_MS = [10 * 60_000, 24 * 60 * 60_000];
    const FIRST_REVIEW_INTERVAL_DAYS = 1;
    const SECOND_REVIEW_INTERVAL_DAYS = 6;
    const LEARNING_EASY_GRADUATION_INTERVAL_DAYS = 3;
    const REVIEW_HARD_INTERVAL_MULTIPLIER = 1.2;
    const REVIEW_EASY_INTERVAL_MULTIPLIER = 1.3;
    const REVIEW_OVERDUE_BONUS_WEIGHT = 0.5;
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

    function beginPreparedSession() {
      return actions.beginPreparedSession?.();
    }

    function modeLabel() {
      return actions.modeLabel?.() || "Центр колоды";
    }

    function normalizeStudySettings(raw = {}) {
      const parsedNewCardsLimit = Number(raw.newCardsLimit);
      return {
        cardSideOrder: raw.cardSideOrder === "back" ? "back" : DEFAULT_STUDY_SETTINGS.cardSideOrder,
        shuffleCards: Boolean(raw.shuffleCards),
        newCardsLimit: Number.isFinite(parsedNewCardsLimit)
          ? Math.max(0, Math.min(200, Math.round(parsedNewCardsLimit)))
          : DEFAULT_STUDY_SETTINGS.newCardsLimit,
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
          newCardsLimit: state.newCardsLimit,
        })
      );
      localStorage.setItem(studySettingsStorageKey(), payload);
    }

    function loadStudySettings() {
      const stored = localStorage.getItem(studySettingsStorageKey());
      if (!stored) {
        state.cardSideOrder = DEFAULT_STUDY_SETTINGS.cardSideOrder;
        state.shuffleCards = DEFAULT_STUDY_SETTINGS.shuffleCards;
        state.newCardsLimit = DEFAULT_STUDY_SETTINGS.newCardsLimit;
        return;
      }
      try {
        const parsed = JSON.parse(stored);
        const normalized = normalizeStudySettings(parsed);
        state.cardSideOrder = normalized.cardSideOrder;
        state.shuffleCards = normalized.shuffleCards;
        state.newCardsLimit = normalized.newCardsLimit;
      } catch (error) {
        state.cardSideOrder = DEFAULT_STUDY_SETTINGS.cardSideOrder;
        state.shuffleCards = DEFAULT_STUDY_SETTINGS.shuffleCards;
        state.newCardsLimit = DEFAULT_STUDY_SETTINGS.newCardsLimit;
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

    function canPersistIntervalSession() {
      return Boolean(state.deck?.progress);
    }

    function isPersistentIntervalSession() {
      return Boolean(state.dueSession?.mode === "interval" && canPersistIntervalSession());
    }

    function isPreviewIntervalSession() {
      return Boolean(state.mode === "interval" && state.dueSession && !isPersistentIntervalSession());
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

    function calculateIntervalAnchorDays(scheduledDays, elapsedDays) {
      const scheduled = Math.max(scheduledDays || 0, FIRST_REVIEW_INTERVAL_DAYS);
      const observed = Math.max(elapsedDays || 0, 0);
      const effectiveElapsed = Math.max(observed, FIRST_REVIEW_INTERVAL_DAYS);
      if (effectiveElapsed <= scheduled) return effectiveElapsed;
      return scheduled + (effectiveElapsed - scheduled) * REVIEW_OVERDUE_BONUS_WEIGHT;
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
      return (isRelearning ? FIRST_REVIEW_INTERVAL_DAYS : LEARNING_EASY_GRADUATION_INTERVAL_DAYS) * 86400_000;
    }

    function previewReviewDelay(stateSnapshot, rating) {
      const quality = RATING_QUALITY[rating];
      const currentEaseFactor = getEaseFactor(stateSnapshot);
      const reviewCount = Math.max(stateSnapshot.reps || 0, 0);
      const scheduledDays = Math.max(stateSnapshot.scheduled_days || 0, 0);
      const elapsedDays = Math.max(stateSnapshot.elapsed_days || 0, 0);

      if (quality < 3) return RELEARNING_STEPS_MS[0];
      if (rating === "hard") {
        const baseInterval = calculateIntervalAnchorDays(scheduledDays, elapsedDays);
        return Math.max(FIRST_REVIEW_INTERVAL_DAYS, baseInterval * REVIEW_HARD_INTERVAL_MULTIPLIER) * 86400_000;
      }

      const nextEase = nextEaseFactor(currentEaseFactor, quality);
      let nextIntervalDays = FIRST_REVIEW_INTERVAL_DAYS;
      if (reviewCount === 1) {
        nextIntervalDays = SECOND_REVIEW_INTERVAL_DAYS;
      } else if (reviewCount > 1) {
        const baseInterval = calculateIntervalAnchorDays(scheduledDays, elapsedDays);
        nextIntervalDays = baseInterval * nextEase;
      }
      if (rating === "easy") nextIntervalDays *= REVIEW_EASY_INTERVAL_MULTIPLIER;
      return nextIntervalDays * 86400_000;
    }

    function formatDelayLabel(delayMs) {
      if (delayMs < 60_000) return "сейчас";
      const totalMinutes = Math.round(delayMs / 60_000);
      if (totalMinutes < 60) return `через ${totalMinutes} мин`;
      const totalHours = Math.round(delayMs / 3_600_000);
      if (totalHours < 48) return `через ${totalHours} ч`;
      const totalDays = Math.round(delayMs / 86_400_000);
      if (totalDays < 30) return `через ${totalDays} д`;
      const totalMonths = Math.round(totalDays / 30);
      return `через ${totalMonths} мес`;
    }

    function buildIntervalRatingPreviews(card) {
      const serverPreview = card?.interval_preview;
      if (
        serverPreview
        && typeof serverPreview.again === "string"
        && typeof serverPreview.hard === "string"
        && typeof serverPreview.good === "string"
        && typeof serverPreview.easy === "string"
      ) {
        return serverPreview;
      }
      const stateSnapshot = normalizeIntervalCardState(card);
      const computeDelay = stateSnapshot.status === "review" ? previewReviewDelay : previewLearningDelay;

      return {
        again: formatDelayLabel(computeDelay(stateSnapshot, "again")),
        hard: formatDelayLabel(computeDelay(stateSnapshot, "hard")),
        good: formatDelayLabel(computeDelay(stateSnapshot, "good")),
        easy: formatDelayLabel(computeDelay(stateSnapshot, "easy")),
      };
    }

    function getIntervalQueueCards() {
      const cards = state.dueSession?.cards || [];
      const startIndex = Number.isFinite(state.dueSession?.current_index) ? state.dueSession.current_index : 0;
      return cards.slice(Math.max(startIndex, 0));
    }

    function buildIntervalQueueBreakdown(cards = getIntervalQueueCards()) {
      return cards.reduce((summary, card) => {
        summary.total += 1;
        const reviewState = card?.state || null;
        if (!reviewState || reviewState.status === "new") {
          summary.newCards += 1;
          return summary;
        }

        if (reviewState.status === "learning") {
          summary.learningCards += 1;
          return summary;
        }

        if (reviewState.status === "relearning") {
          summary.relearningCards += 1;
          return summary;
        }

        summary.reviewCards += 1;
        const dueAtMs = reviewState.due_at ? new Date(reviewState.due_at).getTime() : Number.NaN;
        if (Number.isFinite(dueAtMs) && dueAtMs < Date.now()) summary.overdueCards += 1;
        return summary;
      }, {
        total: 0,
        newCards: 0,
        learningCards: 0,
        relearningCards: 0,
        reviewCards: 0,
        overdueCards: 0,
      });
    }

    function countIntervalRepetitions(cards = state.sessionCards) {
      if (!Array.isArray(cards) || !cards.length) return 0;
      return Math.max(cards.length - new Set(cards.map((card) => card.id)).size, 0);
    }

    function captureSessionSnapshot() {
      return {
        currentIndex: state.currentIndex,
        revealed: state.revealed,
        correct: state.correct,
        incorrect: state.incorrect,
        intervalRatings: { ...state.intervalRatings },
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
      state.intervalRatings = { ...snapshot.intervalRatings };
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
        ? `Завершено · ${total} / ${total}`
        : `${current} / ${total || 0}`;
      if (focusProgressPill) focusProgressPill.textContent = progressText;
      if (focusDeckTitleLabel) {
        const name = state.deck?.name || state.sharedMeta?.name || "Сессия изучения";
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
      return (revealed ? secondaryCardSide() : primaryCardSide()) === 'front' ? 'Лицевая сторона' : 'Обратная сторона';
    }

    async function loadIntervalSession(options = {}) {
      if (!deckId) return null;
      const { restartSession = false } = options;
      if (canPersistIntervalSession()) {
        const params = new URLSearchParams({
          mode: "interval",
          shuffle_cards: state.shuffleCards ? "true" : "false",
          new_cards_limit: String(state.newCardsLimit),
        });
        if (restartSession) params.set("restart_session", "true");
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
        await loadIntervalSession({ restartSession: true });
        startMode(state.mode);
        beginPreparedSession();
        return;
      }
      startMode(state.mode);
      if (state.mode === 'limit') beginPreparedSession();
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
      isPersistentIntervalSession,
      isPreviewIntervalSession,
      getIntervalQueueCards,
      buildIntervalQueueBreakdown,
      countIntervalRepetitions,
      loadIntervalSession,
      startCurrentSessionWithSettings,
      syncFlipPresentation,
    };
  }

  return { createStudySession };
})();
