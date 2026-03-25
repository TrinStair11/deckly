window.studyViewer = (() => {
  function createStudyViewer(ctx) {
    const { state, dom, helpers, actions, config } = ctx;
    const { cardViewer, controlBar } = dom;
    const {
      escapeHtml,
      sharedApi,
      isSessionCompleted,
      currentCard,
      primaryCardSide,
      secondaryCardSide,
      currentSideLabel,
      canUndoSessionAction,
    } = helpers;
    const {
      loadDeck,
      undoLastSessionAction,
      startMode,
      buildTestChoices,
      answerTest,
      flipCurrentCard,
      modeLabel,
    } = actions;
    const { deckId } = config;

    function renderAll() {
      return actions.renderAll?.();
    }

    function setViewerSessionMode(enabled) {
      cardViewer.classList.toggle("viewer-session", Boolean(enabled));
    }

    function renderEmpty(message) {
      setViewerSessionMode(false);
      cardViewer.innerHTML = `<div class="card-body d-flex align-items-center justify-content-center text-center text-secondary">${message}</div>`;
      controlBar.innerHTML = "";
      controlBar.className = "card control-card shadow-sm rounded-4 d-none";
    }

    function renderAccessGate(message = "") {
      setViewerSessionMode(false);
      const deckName = state.sharedMeta?.name || "Private deck";
      cardViewer.innerHTML = `
        <div class="card-body p-4 p-xl-5 d-grid gap-4 align-content-center justify-content-center text-center" style="min-height: 420px;">
          <div class="d-grid gap-2">
            <div><span class="badge text-bg-warning text-dark rounded-pill">Private Deck</span></div>
            <h2 class="h2 mb-0">${escapeHtml(deckName)}</h2>
            <div class="text-secondary">Enter the deck password to unlock this shared study link.</div>
          </div>
          <form class="mx-auto w-100" id="deckAccessForm" style="max-width: 380px;">
            <div class="input-group input-group-lg">
              <input class="form-control bg-dark border-secondary" id="deckAccessPasswordInput" type="password" placeholder="Deck password" required />
              <button class="btn btn-light text-dark" type="submit">Unlock</button>
            </div>
          </form>
          <div class="small fw-semibold ${message ? "text-danger" : "text-secondary"}" id="deckAccessStatus">${escapeHtml(message || "Password is checked on the backend before deck data is returned.")}</div>
        </div>
      `;
      controlBar.innerHTML = "";
      controlBar.className = "card control-card shadow-sm rounded-4 d-none";
      const deckAccessForm = document.getElementById("deckAccessForm");
      if (!deckAccessForm) return;
      deckAccessForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const password = document.getElementById("deckAccessPasswordInput").value.trim();
        if (!password) return;
        try {
          const access = await sharedApi(`/shared/decks/${deckId}/access`, {
            method: "POST",
            body: JSON.stringify({ password }),
            headers: {},
          });
          state.shareAccessToken = access.access_token;
          sessionStorage.setItem(`deck-access-${deckId}`, access.access_token);
          await loadDeck();
        } catch (error) {
          renderAccessGate(error.message);
        }
      });
    }

    function resetToDeckHub() {
      state.mode = "all";
      state.sessionCards = [];
      state.currentIndex = 0;
      state.revealed = false;
      state.started = false;
      state.correct = 0;
      state.incorrect = 0;
      state.missedCardIds = [];
      state.actionHistory = [];
      state.lastAnswer = null;
      state.testChoices = [];
      renderAll();
    }

    function runMissedReview() {
      if (!state.missedCardIds.length) {
        startMode(state.mode);
        return;
      }
      state.sessionCards = state.deck.cards.filter((card) => state.missedCardIds.includes(card.id));
      state.currentIndex = 0;
      state.revealed = false;
      state.correct = 0;
      state.incorrect = 0;
      state.missedCardIds = [];
      state.actionHistory = [];
      state.started = true;
      state.lastAnswer = null;
      if (state.mode === "test" && state.sessionCards[0]) state.testChoices = buildTestChoices(state.sessionCards[0]);
      renderAll();
    }

    function bindCompletionActions(total, missedCount, ringDegrees) {
      const primaryCompletionBtn = document.getElementById("primaryCompletionBtn");
      const practiceAgainBtn = document.getElementById("practiceAgainBtn");
      const restartDeckBtn = document.getElementById("restartDeckBtn");
      const undoCompletionAnswerBtn = document.getElementById("undoCompletionAnswerBtn");
      const returnHubBtn = document.getElementById("returnHubBtn");
      const returnLastQuestionBtn = document.getElementById("returnLastQuestionBtn");
      const resultsRing = document.getElementById("resultsRing");

      if (primaryCompletionBtn) {
        primaryCompletionBtn.addEventListener("click", () => {
          if (missedCount) {
            runMissedReview();
            return;
          }
          startMode(state.mode);
        });
      }
      if (practiceAgainBtn) practiceAgainBtn.addEventListener("click", () => startMode(state.mode));
      if (restartDeckBtn) {
        restartDeckBtn.addEventListener("click", () => {
          state.mode = "all";
          startMode("all");
        });
      }
      if (undoCompletionAnswerBtn) undoCompletionAnswerBtn.addEventListener("click", undoLastSessionAction);
      if (returnHubBtn) returnHubBtn.addEventListener("click", resetToDeckHub);
      if (returnLastQuestionBtn) {
        returnLastQuestionBtn.addEventListener("click", () => {
          if (!total) return;
          state.currentIndex = total - 1;
          renderAll();
        });
      }
      if (resultsRing) {
        resultsRing.style.setProperty("--progress", "0deg");
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            resultsRing.classList.add("is-animated");
            resultsRing.style.setProperty("--progress", ringDegrees);
          });
        });
      }
    }

    function renderCompletion() {
      setViewerSessionMode(false);
      const total = state.sessionCards.length;
      const completed = Math.min(state.correct + state.incorrect, total);
      const successRate = total ? Math.round((state.correct / total) * 100) : 0;
      const ringDegrees = `${Math.round((successRate / 100) * 360)}deg`;
      const missedCount = state.missedCardIds.length;
      const headline = successRate >= 85
        ? "Excellent retention this round."
        : successRate >= 65
          ? "Solid progress. Tighten the weak spots."
          : successRate >= 45
            ? "Good start. Reinforcement will raise mastery."
            : "Session logged. Focus on fundamentals next.";
      const primaryActionLabel = missedCount
        ? `Review ${missedCount} difficult card${missedCount === 1 ? "" : "s"}`
        : "Run this mode again";
      const nextStepTitle = missedCount ? "Best next move" : "Next move";
      const nextStepCopy = missedCount
        ? "Target weak recall while memory is warm, then run a full pass."
        : "No weak cards in this run. A fast second pass helps lock long-term recall.";
      const insight = missedCount
        ? `You mastered ${state.correct} cards. Target the ${missedCount} missed card${missedCount === 1 ? "" : "s"} now to increase retention on the next pass.`
        : "You mastered every reviewed card. Keep spacing consistent to preserve this level across future sessions.";

      cardViewer.innerHTML = `
        <div class="card-body p-4 p-xl-5 d-grid gap-5">
          <div class="results-hero">
            <div class="d-flex justify-content-center justify-content-xl-start">
              <span class="results-kicker"><i class="bi bi-stars"></i>Session complete</span>
            </div>
            <h2 class="results-headline">${headline}</h2>
            <p class="results-subtitle">${state.correct} mastered, ${state.incorrect} need review in <span class="text-light">${escapeHtml(state.deck.name)}</span>. ${completed} cards reviewed in ${modeLabel()}.</p>
          </div>
          <div class="results-shell">
            <div class="completion-layout">
              <section class="completion-summary">
                <div class="completion-core">
                  <div class="d-flex justify-content-center justify-content-xl-start">
                    <div class="results-ring" id="resultsRing" style="--progress: 0deg;">
                      <div class="results-ring-value">
                        <div class="results-ring-number">${successRate}%</div>
                        <div class="results-ring-label">Accuracy</div>
                      </div>
                    </div>
                  </div>
                  <div class="completion-outcome">
                    <div class="completion-outcome-label">Session outcome</div>
                    <div class="completion-outcome-main">${state.correct} mastered, ${state.incorrect} need review</div>
                    <div class="completion-outcome-sub">${completed} of ${total} reviewed in this run.</div>
                  </div>
                </div>
                <div class="completion-metric-grid">
                  <div class="completion-metric mastered">
                    <div class="completion-metric-label">Mastered</div>
                    <div class="completion-metric-value">${state.correct}</div>
                  </div>
                  <div class="completion-metric review">
                    <div class="completion-metric-label">Needs review</div>
                    <div class="completion-metric-value">${state.incorrect}</div>
                  </div>
                  <div class="completion-metric total">
                    <div class="completion-metric-label">Total reviewed</div>
                    <div class="completion-metric-value">${completed}</div>
                  </div>
                </div>
                <div class="results-insight">${insight}</div>
              </section>
              <aside class="completion-actions">
                <div class="completion-action-header">
                  <div class="eyebrow">${nextStepTitle}</div>
                  <h3 class="title">${missedCount ? `Fix ${missedCount} weak card${missedCount === 1 ? "" : "s"} now` : "Keep this retention level stable"}</h3>
                  <p class="copy">${nextStepCopy}</p>
                </div>
                <button class="btn completion-action-primary w-100 results-action-btn primary" type="button" id="primaryCompletionBtn">
                  <span class="action-leading"><i class="bi bi-lightning-charge"></i></span>
                  <span class="action-label">${primaryActionLabel}</span>
                  <span class="action-tag">Recommended</span>
                </button>
                <div class="secondary-action-row">
                  <button class="btn completion-action-secondary results-action-btn" type="button" id="practiceAgainBtn">
                    <i class="bi bi-arrow-repeat"></i>Practice again
                  </button>
                  <button class="btn completion-action-secondary results-action-btn" type="button" id="restartDeckBtn">
                    <i class="bi bi-postcard"></i>Restart full deck
                  </button>
                </div>
                <div class="utility-action-row">
                  ${canUndoSessionAction() ? `
                    <button class="utility-action-btn" type="button" id="undoCompletionAnswerBtn">
                      <i class="bi bi-arrow-counterclockwise"></i>Undo last answer
                    </button>
                  ` : ""}
                  <button class="utility-action-btn" type="button" id="returnHubBtn">
                    <i class="bi bi-grid"></i>Return to deck hub
                  </button>
                  <button class="utility-action-btn" type="button" id="returnLastQuestionBtn">
                    <i class="bi bi-arrow-counterclockwise"></i>Return to last question
                  </button>
                </div>
              </aside>
            </div>
          </div>
        </div>
      `;
      controlBar.innerHTML = "";
      controlBar.className = "card control-card shadow-sm rounded-4 d-none";
      bindCompletionActions(total, missedCount, ringDegrees);
    }

    function bindViewerActions() {
      const flipSurface = cardViewer.querySelector("[data-flip-card]");
      if (flipSurface) {
        flipSurface.addEventListener("click", flipCurrentCard);
        flipSurface.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          flipCurrentCard();
        });
      }

      const undoCardBtn = document.getElementById("undoCardBtn");
      if (undoCardBtn) {
        undoCardBtn.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          undoLastSessionAction();
        });
      }

      if (state.mode === "test") {
        document.querySelectorAll("[data-choice]").forEach((button) => {
          button.addEventListener("click", () => answerTest(button.dataset.choice));
        });
      }
    }

    function renderViewer() {
      if (!state.deck) {
        renderEmpty("Deck is not specified.");
        return;
      }
      if (!state.started && (state.mode === "limit" || state.mode === "interval")) {
        renderEmpty("Configure the selected mode and start the session.");
        return;
      }
      if (!state.sessionCards.length) {
        renderEmpty("This mode currently has no cards to show.");
        return;
      }
      if (isSessionCompleted()) {
        renderCompletion();
        return;
      }

      setViewerSessionMode(true);

      const card = currentCard();
      const showBack = state.revealed;
      const primarySide = primaryCardSide();
      const secondarySide = secondaryCardSide();
      const chipLabel = state.mode === "test" ? "Question" : currentSideLabel(showBack);
      const mainContent = state.mode === "test" ? card.front : (showBack ? card[secondarySide] : card[primarySide]);
      const isFlippable = state.mode !== "test";
      const exitLabelClass = state.reviewExitLabel === "Know it!" ? "know" : "dontknow";
      const showTopProgress = state.mode !== "all" && state.mode !== "limit";
      const headerRowClass = showTopProgress
        ? "d-flex justify-content-between align-items-center gap-3"
        : "d-flex justify-content-start align-items-center gap-3";

      cardViewer.innerHTML = `
        ${state.reviewExitLabel ? `<div class="review-exit-label ${exitLabelClass}"><span>${state.reviewExitLabel}</span></div>` : ""}
        <div class="card-body review-view-body">
          <div class="${headerRowClass}">
            <span class="badge ${showBack ? "text-bg-success" : "text-bg-secondary"} rounded-pill" id="reviewStateBadge">${chipLabel}</span>
            ${showTopProgress ? `<span class="text-secondary">${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</span>` : ""}
          </div>
          <div class="flip-stage">
            ${state.mode === "test" ? `
              <div class="d-grid gap-3 text-center align-content-center justify-content-center" style="min-height: 260px;">
                ${card.image_url ? `<div class="viewer-media"><img src="${escapeHtml(card.image_url)}" alt="Card visual" /></div>` : ""}
                <div class="review-main-text">${escapeHtml(mainContent)}</div>
                <div class="row g-2" id="choiceGrid">
                  ${state.testChoices.map((choice) => {
                    let classes = "btn btn-outline-light text-start h-100";
                    if (state.lastAnswer) {
                      if (choice === card.back) classes = "btn btn-success text-start h-100";
                      if (choice === state.lastAnswer.choice && !state.lastAnswer.correct) classes = "btn btn-danger text-start h-100";
                    }
                    return `<div class="col-12 col-md-6"><button class="${classes}" type="button" data-choice="${escapeHtml(choice)}">${escapeHtml(choice)}</button></div>`;
                  }).join("")}
                </div>
              </div>
            ` : `
              <div class="flip-shell">
                <div class="flip-surface ${showBack ? "is-flipped" : ""}" ${isFlippable ? 'data-flip-card="true" role="button" tabindex="0"' : ""}>
                  <div class="flip-face front ${card.image_url ? "has-media" : ""}">
                    <div class="review-card-content">
                      ${card.image_url ? `<div class="viewer-media"><img src="${escapeHtml(card.image_url)}" alt="Card visual" /></div>` : ""}
                      <div class="review-main-text">${escapeHtml(card[primarySide])}</div>
                    </div>
                  </div>
                  <div class="flip-face back ${card.image_url ? "has-media" : ""}">
                    <div class="review-card-content">
                      ${card.image_url ? `<div class="viewer-media"><img src="${escapeHtml(card.image_url)}" alt="Card visual" /></div>` : ""}
                      <div class="review-main-text">${escapeHtml(card[secondarySide])}</div>
                    </div>
                  </div>
                </div>
                ${canUndoSessionAction() ? `
                  <button class="viewer-undo-btn" type="button" id="undoCardBtn" aria-label="Undo last answer" title="Undo last answer">
                    <i class="bi bi-arrow-counterclockwise"></i>
                  </button>
                ` : ""}
              </div>
            `}
          </div>
        </div>
      `;

      bindViewerActions();
    }

    return {
      setViewerSessionMode,
      renderAccessGate,
      renderViewer,
    };
  }

  return { createStudyViewer };
})();
