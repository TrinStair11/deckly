window.studyActions = (() => {
  function createStudyActions(ctx) {
    const { state, helpers, actions } = ctx;
    const {
      api,
      currentCard,
      shuffle,
      syncFlipPresentation,
      captureSessionSnapshot,
      pushSessionUndo,
    } = helpers;

    function renderAll() {
      return actions.renderAll?.();
    }

    function renderControls() {
      return actions.renderControls?.();
    }

    function buildTestChoices(card) {
      const distractors = shuffle(state.deck.cards.filter((item) => item.id !== card.id).map((item) => item.back)).slice(0, 3);
      return shuffle([card.back, ...distractors]);
    }

    function resetSessionState(modeId) {
      state.mode = modeId;
      state.currentIndex = 0;
      state.revealed = false;
      state.correct = 0;
      state.incorrect = 0;
      state.missedCardIds = [];
      state.actionHistory = [];
      state.started = false;
      state.lastAnswer = null;
      state.testChoices = [];
    }

    function startMode(modeId) {
      resetSessionState(modeId);

      if (!state.deck) {
        renderAll();
        return;
      }

      if (modeId === "all") {
        state.sessionCards = state.shuffleCards ? shuffle(state.deck.cards) : [...state.deck.cards];
        state.started = true;
      } else if (modeId === "limit") {
        const source = state.shuffleCards ? shuffle(state.deck.cards) : [...state.deck.cards];
        state.sessionCards = source.slice(0, state.sessionLimit === "all" ? source.length : Number(state.sessionLimit));
      } else if (modeId === "interval") {
        state.sessionCards = [...(state.dueSession?.cards || [])];
        state.currentIndex = state.dueSession?.current_index || 0;
        state.intervalSessionId = state.dueSession?.session_id || "";
        state.started = true;
      } else if (modeId === "test") {
        state.sessionCards = state.shuffleCards ? shuffle(state.deck.cards) : [...state.deck.cards];
        state.started = true;
        if (state.sessionCards[0]) state.testChoices = buildTestChoices(state.sessionCards[0]);
      }

      renderAll();
    }

    function flipCurrentCard() {
      if (!state.deck || !state.mode || !state.sessionCards.length) return;
      if (!state.started && (state.mode === "limit" || state.mode === "interval")) return;
      if (state.currentIndex >= state.sessionCards.length) return;
      if (state.mode === "test") return;
      state.revealed = !state.revealed;
      syncFlipPresentation();
      if (state.mode === "interval") renderControls();
    }

    function animateReviewExit(direction, onFinish) {
      if (state.reviewAnimating) return;
      const viewer = document.getElementById("cardViewer");
      if (!viewer) {
        onFinish();
        return;
      }
      state.reviewAnimating = true;
      state.reviewExitLabel = direction === "know" ? "Know it!" : "Don't know yet!";
      renderAll();
      const activeViewer = document.getElementById("cardViewer");
      activeViewer.classList.remove("review-hold", "exit-know", "exit-dontknow");
      const exitClass = direction === "know" ? "exit-know" : "exit-dontknow";
      const finish = () => {
        activeViewer.removeEventListener("animationend", finish);
        activeViewer.classList.remove("review-hold", "exit-know", "exit-dontknow");
        state.reviewAnimating = false;
        state.reviewExitLabel = "";
        onFinish();
      };
      activeViewer.classList.add("review-hold");
      window.setTimeout(() => {
        if (!state.reviewAnimating) return;
        activeViewer.addEventListener("animationend", finish, { once: true });
        activeViewer.classList.remove("review-hold");
        activeViewer.classList.add(exitClass);
      }, 500);
    }

    function completeSelfCheck(knows) {
      if (state.reviewAnimating) return;
      const snapshot = captureSessionSnapshot();
      animateReviewExit(knows ? "know" : "dontknow", () => {
        pushSessionUndo(snapshot);
        if (knows) {
          state.correct += 1;
        } else {
          state.incorrect += 1;
          const card = currentCard();
          if (card && !state.missedCardIds.includes(card.id)) state.missedCardIds.push(card.id);
        }

        if (state.currentIndex < state.sessionCards.length - 1) {
          state.currentIndex += 1;
          state.revealed = false;
        } else {
          state.currentIndex = state.sessionCards.length;
        }
        renderAll();
      });
    }

    async function submitIntervalRating(rating) {
      const card = currentCard();
      if (!card) return;
      let nextIndex = state.currentIndex + 1;
      if (state.me) {
        const sessionId = state.intervalSessionId || (window.crypto?.randomUUID?.() || `interval-${Date.now()}`);
        state.intervalSessionId = sessionId;
        const result = await api("/reviews/submit", {
          method: "POST",
          body: JSON.stringify({
            deck_id: state.deck.id,
            card_id: card.id,
            rating,
            session_id: sessionId,
          }),
        });
        if (result?.progress) {
          state.deck.progress = result.progress;
        }
        if (typeof result?.session_current_index === "number") {
          nextIndex = result.session_current_index;
        }
      }
      if (rating === "again" || rating === "hard") {
        state.incorrect += 1;
        if (!state.missedCardIds.includes(card.id)) state.missedCardIds.push(card.id);
      } else {
        state.correct += 1;
      }
      if (nextIndex < state.sessionCards.length) {
        state.currentIndex = nextIndex;
        state.revealed = false;
      } else {
        state.currentIndex = state.sessionCards.length;
      }
      renderAll();
    }

    function answerTest(choice) {
      const card = currentCard();
      if (!card || state.lastAnswer) return;
      const snapshot = captureSessionSnapshot();
      const correct = choice === card.back;
      state.lastAnswer = { choice, correct };
      if (correct) {
        state.correct += 1;
      } else {
        state.incorrect += 1;
        if (!state.missedCardIds.includes(card.id)) state.missedCardIds.push(card.id);
      }
      pushSessionUndo(snapshot);
      renderAll();
    }

    function nextTestCard() {
      if (state.currentIndex < state.sessionCards.length - 1) {
        state.currentIndex += 1;
        state.lastAnswer = null;
        state.testChoices = buildTestChoices(currentCard());
      } else {
        state.currentIndex = state.sessionCards.length;
      }
      renderAll();
    }

    return {
      buildTestChoices,
      startMode,
      flipCurrentCard,
      completeSelfCheck,
      submitIntervalRating,
      answerTest,
      nextTestCard,
    };
  }

  return { createStudyActions };
})();
