window.studyControls = (() => {
  function createStudyControls(ctx) {
    const { state, dom, helpers, actions } = ctx;
    const { controlBar } = dom;
    const {
      isSessionActive,
      canUndoSessionAction,
      primaryCardSide,
      captureSessionSnapshot,
      pushSessionUndo,
    } = helpers;
    const {
      toggleFocusMode,
      completeSelfCheck,
      flipCurrentCard,
      submitIntervalRating,
      nextTestCard,
      undoLastSessionAction,
      saveStudySettings,
      startCurrentSessionWithSettings,
      renderViewer,
    } = actions;

    function renderSettingsPanelContent() {
      return `
        <div class="d-grid gap-3">
          <div>
            <div class="small text-secondary text-uppercase mb-2">Card side order</div>
            <div class="d-grid gap-2">
              <label class="form-check">
                <input class="form-check-input" type="radio" name="cardSideOrder" value="front" ${state.cardSideOrder === "front" ? "checked" : ""}>
                <span class="form-check-label">Front first</span>
              </label>
              <label class="form-check">
                <input class="form-check-input" type="radio" name="cardSideOrder" value="back" ${state.cardSideOrder === "back" ? "checked" : ""}>
                <span class="form-check-label">Back first</span>
              </label>
            </div>
          </div>
          <div>
            <div class="small text-secondary text-uppercase mb-2">Order</div>
            <div class="form-check form-switch">
              <input class="form-check-input" type="checkbox" role="switch" id="shuffleCardsToggle" ${state.shuffleCards ? "checked" : ""}>
              <label class="form-check-label" for="shuffleCardsToggle">Shuffle cards</label>
            </div>
            <div class="small text-secondary mt-2">Shuffle is applied when a session starts or restarts.</div>
          </div>
        </div>
      `;
    }

    function renderSettingsShell() {
      return `
        <div class="settings-shell" data-settings-shell>
          <button class="btn btn-outline-light utility-btn" type="button" id="studySettingsBtn" title="Study settings" aria-label="Study settings" aria-expanded="${state.settingsOpen ? "true" : "false"}">
            <i class="bi bi-sliders"></i>
          </button>
          ${state.settingsOpen ? `
            <div class="study-settings-panel">
              ${renderSettingsPanelContent()}
            </div>
          ` : ""}
        </div>
      `;
    }

    function bindSettingsControls() {
      const studySettingsBtn = document.getElementById("studySettingsBtn");
      const shuffleCardsToggle = document.getElementById("shuffleCardsToggle");

      if (studySettingsBtn) {
        studySettingsBtn.addEventListener("click", (event) => {
          event.stopPropagation();
          state.settingsOpen = !state.settingsOpen;
          renderControls();
        });
      }

      document.querySelectorAll('input[name="cardSideOrder"]').forEach((input) => {
        input.addEventListener("change", () => {
          state.cardSideOrder = input.value;
          saveStudySettings();
          state.revealed = false;
          renderViewer();
          renderControls();
        });
      });

      if (shuffleCardsToggle) {
        shuffleCardsToggle.addEventListener("change", () => {
          state.shuffleCards = shuffleCardsToggle.checked;
          saveStudySettings();
          startCurrentSessionWithSettings();
        });
      }
    }

    function renderFocusToggleButton() {
      if (!isSessionActive()) return "";
      const isOn = Boolean(state.focusMode);
      const label = isOn ? "Exit fullscreen focus mode" : "Open fullscreen focus mode";
      const icon = isOn ? "bi-fullscreen-exit" : "bi-arrows-fullscreen";
      return `
        <button class="btn btn-outline-light utility-btn" type="button" id="focusModeBtn" title="${label}" aria-label="${label}" aria-pressed="${isOn ? "true" : "false"}">
          <i class="bi ${icon}"></i>
        </button>
      `;
    }

    function bindFocusControls() {
      const focusModeBtn = document.getElementById("focusModeBtn");
      if (focusModeBtn) {
        focusModeBtn.addEventListener("click", () => {
          toggleFocusMode();
        });
      }
    }

    function renderControls() {
      const shouldHide = !state.deck || !state.mode || !state.sessionCards.length
        || (!state.started && (state.mode === "limit" || state.mode === "interval"))
        || state.currentIndex >= state.sessionCards.length;
      if (shouldHide) {
        controlBar.innerHTML = "";
        controlBar.className = "card control-card shadow-sm rounded-4 d-none";
        return;
      }

      controlBar.className = "card control-card shadow-sm rounded-4";

      if (state.mode === "all" || state.mode === "limit") {
        if (state.focusMode) {
          controlBar.innerHTML = `
            <div class="card-body focus-control-body" data-settings-shell>
              <div class="focus-review-controls">
                <button class="btn focus-answer-btn negative" type="button" id="dontKnowBtn" aria-label="I don't know">
                  <i class="bi bi-x-lg"></i><span>Don't know</span>
                </button>
                <button class="btn focus-answer-btn neutral" type="button" id="flipReviewBtn" aria-label="Flip card">
                  <i class="bi bi-arrow-repeat"></i><span>${state.revealed ? `Show ${primaryCardSide() === "front" ? "Front" : "Back"}` : "Flip card"}</span>
                </button>
                <button class="btn focus-answer-btn positive" type="button" id="knowBtn" aria-label="I know it">
                  <i class="bi bi-check-lg"></i><span>Know it</span>
                </button>
              </div>
              <div class="focus-utility-row">
                <div class="focus-progress-mini">${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
                <div class="dropdown focus-more-menu">
                  <button class="btn focus-more-btn" type="button" id="focusMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="More actions">
                    <i class="bi bi-three-dots"></i>
                  </button>
                  <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                    <li><button class="dropdown-item rounded-3 ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="focusUndoAction" ${canUndoSessionAction() ? "" : "disabled"}>Undo last answer</button></li>
                    <li><button class="dropdown-item rounded-3" type="button" id="focusSettingsAction">Study settings</button></li>
                    ${state.ownerAccess ? `<li><a class="dropdown-item rounded-3" href="/deck.html?id=${state.deck.id}">Open deck editor</a></li>` : ""}
                    <li><button class="dropdown-item rounded-3" type="button" id="focusExitAction">Exit fullscreen</button></li>
                  </ul>
                </div>
              </div>
              ${state.settingsOpen ? `<div class="study-settings-panel focus-settings-panel">${renderSettingsPanelContent()}</div>` : ""}
            </div>
          `;
          document.getElementById("dontKnowBtn").addEventListener("click", () => completeSelfCheck(false));
          document.getElementById("knowBtn").addEventListener("click", () => completeSelfCheck(true));
          document.getElementById("flipReviewBtn").addEventListener("click", flipCurrentCard);
          const focusUndoAction = document.getElementById("focusUndoAction");
          if (focusUndoAction && !focusUndoAction.disabled) focusUndoAction.addEventListener("click", undoLastSessionAction);
          const focusSettingsAction = document.getElementById("focusSettingsAction");
          if (focusSettingsAction) {
            focusSettingsAction.addEventListener("click", () => {
              state.settingsOpen = !state.settingsOpen;
              renderControls();
            });
          }
          const focusExitAction = document.getElementById("focusExitAction");
          if (focusExitAction) focusExitAction.addEventListener("click", () => toggleFocusMode(false));
          bindSettingsControls();
          return;
        }

        controlBar.className = "card control-card review-control-card shadow-sm rounded-4";
        controlBar.innerHTML = `
          <div class="review-control-shell" data-settings-shell>
            <div class="card-body review-control-layout">
              <div class="review-side-meta">
                <span class="control-mode-pill"><i class="bi bi-check2-square"></i>Self-check</span>
              </div>
              <div class="review-answer-cluster">
                <button class="btn review-answer-btn negative" type="button" id="dontKnowBtn" aria-label="I don't know">
                  <i class="bi bi-x-lg"></i><span>Don't know</span>
                </button>
                <div class="review-progress-core">${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
                <button class="btn review-answer-btn positive" type="button" id="knowBtn" aria-label="I know it">
                  <i class="bi bi-check-lg"></i><span>Know it</span>
                </button>
              </div>
              <div class="review-side-meta right">
                <div class="review-utility">
                  ${renderFocusToggleButton()}
                  <div class="dropdown">
                    <button class="btn review-more-btn" type="button" id="reviewMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="More actions">
                      <i class="bi bi-three-dots"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                      <li><button class="dropdown-item rounded-3" type="button" id="flipReviewBtn">Flip card</button></li>
                      <li><button class="dropdown-item rounded-3" type="button" id="reviewSettingsBtn">Study settings</button></li>
                      ${state.ownerAccess ? `<li><a class="dropdown-item rounded-3" href="/deck.html?id=${state.deck.id}">Open deck editor</a></li>` : ""}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
            ${state.settingsOpen ? `<div class="study-settings-panel review-settings-panel">${renderSettingsPanelContent()}</div>` : ""}
          </div>
        `;
        document.getElementById("dontKnowBtn").addEventListener("click", () => completeSelfCheck(false));
        document.getElementById("knowBtn").addEventListener("click", () => completeSelfCheck(true));
        document.getElementById("flipReviewBtn").addEventListener("click", flipCurrentCard);
        const reviewSettingsBtn = document.getElementById("reviewSettingsBtn");
        if (reviewSettingsBtn) {
          reviewSettingsBtn.addEventListener("click", () => {
            state.settingsOpen = !state.settingsOpen;
            renderControls();
          });
        }
        bindSettingsControls();
        bindFocusControls();
        return;
      }

      if (state.mode === "interval") {
        controlBar.innerHTML = !state.revealed ? `
          <div class="card-body py-2 px-3 d-flex flex-column flex-xl-row justify-content-between align-items-center gap-2">
            <div>
              <div class="small text-secondary text-uppercase">Interval review</div>
              <div class="fw-semibold">Reveal answer, then rate recall quality.</div>
            </div>
            <div class="d-flex align-items-center gap-2">
              <button class="btn btn-light text-dark" type="button" id="showIntervalBtn">Show Answer</button>
              ${renderFocusToggleButton()}
              ${renderSettingsShell()}
            </div>
          </div>
        ` : `
          <div class="card-body py-2 px-3 d-grid gap-2">
            <div class="d-flex flex-column flex-xl-row justify-content-between align-items-xl-center gap-2">
              <div>
                <div class="small text-secondary text-uppercase">Interval review</div>
                <div class="fw-semibold">Rate quality to schedule next review.</div>
              </div>
              <div class="d-flex align-items-center utility-cluster">${renderFocusToggleButton()}${renderSettingsShell()}</div>
            </div>
            <div class="interval-rating-group mx-auto">
              <button class="btn btn-danger response-btn interval-rating-btn" type="button" data-rating="again">1 Again</button>
              <button class="btn btn-warning response-btn interval-rating-btn" type="button" data-rating="hard">2 Hard</button>
              <button class="btn btn-secondary response-btn interval-rating-btn" type="button" data-rating="good">3 Good</button>
              <button class="btn btn-success response-btn interval-rating-btn" type="button" data-rating="easy">4 Easy</button>
              <button class="btn btn-primary response-btn interval-rating-btn" type="button" data-rating="perfect">5 Perfect</button>
            </div>
          </div>
        `;
        const showIntervalBtn = document.getElementById("showIntervalBtn");
        if (showIntervalBtn) showIntervalBtn.addEventListener("click", flipCurrentCard);
        controlBar.querySelectorAll("[data-rating]").forEach((button) => button.addEventListener("click", () => submitIntervalRating(button.dataset.rating)));
        bindSettingsControls();
        bindFocusControls();
        return;
      }

      if (state.mode === "test") {
        controlBar.innerHTML = `
          <div class="card-body py-2 px-3 d-flex flex-column flex-xl-row justify-content-between align-items-xl-center gap-2">
            <div class="study-counter"><span class="kicker">Current Card</span>${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
            <div class="d-flex align-items-center utility-cluster">
              <button class="btn btn-outline-light utility-btn ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="undoTestBtn" title="Undo last answer" ${canUndoSessionAction() ? "" : "disabled"}>
                <i class="bi bi-arrow-counterclockwise"></i>
              </button>
              <button class="btn ${state.lastAnswer ? "btn-light text-dark" : "btn-outline-light"}" type="button" id="testNextBtn">${state.lastAnswer ? "Next Question" : "Skip"}</button>
              ${renderFocusToggleButton()}
              ${renderSettingsShell()}
            </div>
          </div>
        `;
        document.getElementById("testNextBtn").addEventListener("click", () => {
          const snapshot = captureSessionSnapshot();
          if (!state.lastAnswer) state.incorrect += 1;
          pushSessionUndo(snapshot);
          nextTestCard();
        });
        const undoTestBtn = document.getElementById("undoTestBtn");
        if (undoTestBtn && !undoTestBtn.disabled) undoTestBtn.addEventListener("click", undoLastSessionAction);
        bindSettingsControls();
        bindFocusControls();
      }
    }

    return {
      renderSettingsPanelContent,
      renderSettingsShell,
      bindSettingsControls,
      renderFocusToggleButton,
      bindFocusControls,
      renderControls,
    };
  }

  return { createStudyControls };
})();
