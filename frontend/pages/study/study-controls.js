window.studyControls = (() => {
  function createStudyControls(ctx) {
    const { state, dom, helpers, actions } = ctx;
    const { controlBar } = dom;
    const {
      isSessionActive,
      canUndoSessionAction,
      primaryCardSide,
      currentCard,
      buildIntervalRatingPreviews,
      isPreviewIntervalSession,
      captureSessionSnapshot,
      pushSessionUndo,
    } = helpers;
    const {
      toggleFocusMode,
      completeSelfCheck,
      beginPreparedSession,
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
            <div class="small text-secondary text-uppercase mb-2">Порядок сторон карточки</div>
            <div class="d-grid gap-2">
              <label class="form-check">
                <input class="form-check-input" type="radio" name="cardSideOrder" value="front" ${state.cardSideOrder === "front" ? "checked" : ""}>
                <span class="form-check-label">Сначала лицевая сторона</span>
              </label>
              <label class="form-check">
                <input class="form-check-input" type="radio" name="cardSideOrder" value="back" ${state.cardSideOrder === "back" ? "checked" : ""}>
                <span class="form-check-label">Сначала обратная сторона</span>
              </label>
            </div>
          </div>
          <div>
            <div class="small text-secondary text-uppercase mb-2">Порядок</div>
            <div class="form-check form-switch">
              <input class="form-check-input" type="checkbox" role="switch" id="shuffleCardsToggle" ${state.shuffleCards ? "checked" : ""}>
              <label class="form-check-label" for="shuffleCardsToggle">Перемешивать карточки</label>
            </div>
            <div class="small text-secondary mt-2">Перемешивание применяется при старте или перезапуске сессии.</div>
          </div>
          ${state.mode === "interval" && !isPreviewIntervalSession() ? `
            <div>
              <div class="small text-secondary text-uppercase mb-2">Новых карточек за интервальную сессию</div>
              <div class="d-flex gap-2 flex-wrap">
                ${[0, 5, 10, 20].map((value) => `
                  <button
                    class="btn ${state.newCardsLimit === value ? "btn-light text-dark" : "btn-outline-light"} rounded-pill btn-sm"
                    type="button"
                    data-study-new-cards-limit="${value}"
                  >
                    ${value}
                  </button>
                `).join("")}
              </div>
              <div class="small text-secondary mt-2">Изменение этого параметра перезапустит очередь с новым набором карточек к повторению и новых карточек.</div>
            </div>
          ` : ""}
        </div>
      `;
    }

    function renderSettingsShell() {
      return `
        <div class="settings-shell" data-settings-shell>
          <button class="btn btn-outline-light utility-btn" type="button" id="studySettingsBtn" title="Настройки изучения" aria-label="Настройки изучения" aria-expanded="${state.settingsOpen ? "true" : "false"}">
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

      document.querySelectorAll("[data-study-new-cards-limit]").forEach((button) => {
        button.addEventListener("click", () => {
          const nextValue = Number(button.dataset.studyNewCardsLimit);
          if (!Number.isFinite(nextValue)) return;
          state.newCardsLimit = nextValue;
          saveStudySettings();
          startCurrentSessionWithSettings();
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
      const label = isOn ? "Выйти из полноэкранного режима фокуса" : "Открыть полноэкранный режим фокуса";
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

    function intervalProgressLabel() {
      return `${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}`;
    }

    function intervalControlHint(previewOnly) {
      if (!state.revealed) {
        return previewOnly
          ? "Переверните карточку и попробуйте процесс оценки. Эти оценки не сохраняются."
          : "Переверните карточку и оцените качество вспоминания, чтобы назначить следующий повтор.";
      }
      return previewOnly
        ? "Только предпросмотр. Оценки не изменят ваше персональное расписание."
        : "Оценивайте честно по качеству вспоминания, а не по желаемому интервалу.";
    }

    function renderIntervalControlContext(previewOnly) {
      return `
        <div class="control-context">
          <span class="control-mode-pill"><i class="bi bi-clock-history"></i>${previewOnly ? "Предпросмотр интервалов" : "Интервальное повторение"}</span>
          <div class="control-hint">${intervalControlHint(previewOnly)}</div>
        </div>
      `;
    }

    function renderIntervalRatingButtons(ratingPreviews, variant = "review") {
      const baseClass = variant === "focus" ? "focus-answer-btn interval-focus-rating-btn" : "review-answer-btn interval-rating-pill";
      return `
        <button class="btn ${baseClass} negative" type="button" data-rating="again">
          <span class="interval-rating-main">1 Снова</span>
          <span class="interval-rating-sub">${ratingPreviews.again}</span>
        </button>
        <button class="btn ${baseClass} warning" type="button" data-rating="hard">
          <span class="interval-rating-main">2 Трудно</span>
          <span class="interval-rating-sub">${ratingPreviews.hard}</span>
        </button>
        <button class="btn ${baseClass} info" type="button" data-rating="good">
          <span class="interval-rating-main">3 Хорошо</span>
          <span class="interval-rating-sub">${ratingPreviews.good}</span>
        </button>
        <button class="btn ${baseClass} positive" type="button" data-rating="easy">
          <span class="interval-rating-main">4 Легко</span>
          <span class="interval-rating-sub">${ratingPreviews.easy}</span>
        </button>
      `;
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
                <button class="btn focus-answer-btn negative" type="button" id="dontKnowBtn" aria-label="Не знаю">
                  <i class="bi bi-x-lg"></i><span>Не знаю</span>
                </button>
                <button class="btn focus-answer-btn neutral" type="button" id="flipReviewBtn" aria-label="Перевернуть карточку">
                  <i class="bi bi-arrow-repeat"></i><span>${state.revealed ? `Показать ${primaryCardSide() === "front" ? "лицевую сторону" : "обратную сторону"}` : "Перевернуть карточку"}</span>
                </button>
                <button class="btn focus-answer-btn positive" type="button" id="knowBtn" aria-label="Знаю">
                  <i class="bi bi-check-lg"></i><span>Знаю</span>
                </button>
              </div>
              <div class="focus-utility-row">
                <div class="focus-progress-mini">${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
                <div class="dropdown focus-more-menu">
                  <button class="btn focus-more-btn" type="button" id="focusMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="Ещё действия">
                    <i class="bi bi-three-dots"></i>
                  </button>
                  <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                    <li><button class="dropdown-item rounded-3 ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="focusUndoAction" ${canUndoSessionAction() ? "" : "disabled"}>Отменить последний ответ</button></li>
                    <li><button class="dropdown-item rounded-3" type="button" id="focusSettingsAction">Настройки изучения</button></li>
                    <li><a class="dropdown-item rounded-3" href="/deck?id=${state.deck.id}&view=interval">Открыть список слов</a></li>
                    <li><button class="dropdown-item rounded-3" type="button" id="focusExitAction">Выйти из полноэкранного режима</button></li>
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
                <span class="control-mode-pill"><i class="bi bi-check2-square"></i>Самопроверка</span>
              </div>
              <div class="review-answer-cluster">
                <button class="btn review-answer-btn negative" type="button" id="dontKnowBtn" aria-label="Не знаю">
                  <i class="bi bi-x-lg"></i><span>Не знаю</span>
                </button>
                <div class="review-progress-core">${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
                <button class="btn review-answer-btn positive" type="button" id="knowBtn" aria-label="Знаю">
                  <i class="bi bi-check-lg"></i><span>Знаю</span>
                </button>
              </div>
              <div class="review-side-meta right">
                <div class="review-utility">
                  ${renderFocusToggleButton()}
                  <div class="dropdown">
                    <button class="btn review-more-btn" type="button" id="reviewMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="Ещё действия">
                      <i class="bi bi-three-dots"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                      <li><button class="dropdown-item rounded-3" type="button" id="flipReviewBtn">Перевернуть карточку</button></li>
                      <li><button class="dropdown-item rounded-3" type="button" id="reviewSettingsBtn">Настройки изучения</button></li>
                      <li><a class="dropdown-item rounded-3" href="/deck?id=${state.deck.id}&view=interval">Открыть список слов</a></li>
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
        const ratingPreviews = buildIntervalRatingPreviews(currentCard());
        const previewOnly = isPreviewIntervalSession();
        if (state.focusMode) {
          controlBar.innerHTML = `
            <div class="card-body focus-control-body" data-settings-shell>
              <div class="focus-review-controls interval-focus-controls ${state.revealed ? "is-rating" : "is-single"}">
                ${state.revealed
                  ? renderIntervalRatingButtons(ratingPreviews, "focus")
                  : `<button class="btn focus-answer-btn neutral interval-focus-single-btn" type="button" id="showIntervalBtn">
                      <i class="bi bi-arrow-repeat"></i><span>Показать ответ</span>
                    </button>`}
              </div>
              <div class="focus-utility-row">
                <div class="focus-progress-mini">${intervalProgressLabel()}</div>
                <div class="dropdown focus-more-menu">
                  <button class="btn focus-more-btn" type="button" id="focusMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="Ещё действия">
                    <i class="bi bi-three-dots"></i>
                  </button>
                  <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                    <li><button class="dropdown-item rounded-3" type="button" id="flipReviewBtn">${state.revealed ? `Показать ${primaryCardSide() === "front" ? "лицевую сторону" : "обратную сторону"}` : "Показать ответ"}</button></li>
                    <li><button class="dropdown-item rounded-3 ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="focusUndoAction" ${canUndoSessionAction() ? "" : "disabled"}>Отменить последнюю оценку</button></li>
                    <li><button class="dropdown-item rounded-3" type="button" id="focusSettingsAction">Настройки изучения</button></li>
                    <li><a class="dropdown-item rounded-3" href="/deck?id=${state.deck.id}&view=interval">Открыть список слов</a></li>
                    <li><button class="dropdown-item rounded-3" type="button" id="focusExitAction">Выйти из полноэкранного режима</button></li>
                  </ul>
                </div>
              </div>
              ${state.settingsOpen ? `<div class="study-settings-panel focus-settings-panel">${renderSettingsPanelContent()}</div>` : ""}
            </div>
          `;
          const showIntervalBtn = document.getElementById("showIntervalBtn");
          if (showIntervalBtn) showIntervalBtn.addEventListener("click", flipCurrentCard);
          const flipReviewBtn = document.getElementById("flipReviewBtn");
          if (flipReviewBtn) flipReviewBtn.addEventListener("click", flipCurrentCard);
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
          controlBar.querySelectorAll("[data-rating]").forEach((button) => button.addEventListener("click", () => submitIntervalRating(button.dataset.rating)));
          bindSettingsControls();
          return;
        }

        controlBar.className = "card control-card review-control-card shadow-sm rounded-4";
        controlBar.innerHTML = `
          <div class="review-control-shell" data-settings-shell>
            <div class="card-body review-control-layout interval-control-layout">
              <div class="review-side-meta">
                ${renderIntervalControlContext(previewOnly)}
              </div>
              <div class="review-answer-cluster interval-answer-cluster ${state.revealed ? "is-rating" : "is-single"}">
                ${state.revealed
                  ? renderIntervalRatingButtons(ratingPreviews, "review")
                  : `<button class="btn review-answer-btn neutral interval-single-btn" type="button" id="showIntervalBtn">
                      <i class="bi bi-arrow-repeat"></i><span>Показать ответ</span>
                    </button>`}
              </div>
              <div class="review-side-meta right">
                <div class="review-progress-core interval-progress-core">${intervalProgressLabel()}</div>
                <div class="review-utility">
                  ${renderFocusToggleButton()}
                  <div class="dropdown">
                    <button class="btn review-more-btn" type="button" id="reviewMoreBtn" data-bs-toggle="dropdown" aria-expanded="false" title="Ещё действия">
                      <i class="bi bi-three-dots"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end rounded-4 p-2">
                      <li><button class="dropdown-item rounded-3" type="button" id="flipReviewBtn">${state.revealed ? `Показать ${primaryCardSide() === "front" ? "лицевую сторону" : "обратную сторону"}` : "Показать ответ"}</button></li>
                      <li><button class="dropdown-item rounded-3 ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="reviewUndoBtn" ${canUndoSessionAction() ? "" : "disabled"}>Отменить последнюю оценку</button></li>
                      <li><button class="dropdown-item rounded-3" type="button" id="reviewSettingsBtn">Настройки изучения</button></li>
                      <li><a class="dropdown-item rounded-3" href="/deck?id=${state.deck.id}&view=interval">Открыть список слов</a></li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
            ${state.settingsOpen ? `<div class="study-settings-panel review-settings-panel">${renderSettingsPanelContent()}</div>` : ""}
          </div>
        `;
        const showIntervalBtn = document.getElementById("showIntervalBtn");
        if (showIntervalBtn) showIntervalBtn.addEventListener("click", flipCurrentCard);
        const flipReviewBtn = document.getElementById("flipReviewBtn");
        if (flipReviewBtn) flipReviewBtn.addEventListener("click", flipCurrentCard);
        const reviewUndoBtn = document.getElementById("reviewUndoBtn");
        if (reviewUndoBtn && !reviewUndoBtn.disabled) reviewUndoBtn.addEventListener("click", undoLastSessionAction);
        const reviewSettingsBtn = document.getElementById("reviewSettingsBtn");
        if (reviewSettingsBtn) {
          reviewSettingsBtn.addEventListener("click", () => {
            state.settingsOpen = !state.settingsOpen;
            renderControls();
          });
        }
        controlBar.querySelectorAll("[data-rating]").forEach((button) => button.addEventListener("click", () => submitIntervalRating(button.dataset.rating)));
        bindSettingsControls();
        bindFocusControls();
        return;
      }

      if (state.mode === "test") {
        controlBar.innerHTML = `
          <div class="card-body py-2 px-3 d-flex flex-column flex-xl-row justify-content-between align-items-xl-center gap-2">
            <div class="study-counter"><span class="kicker">Текущая карточка</span>${Math.min(state.currentIndex + 1, state.sessionCards.length)} / ${state.sessionCards.length}</div>
            <div class="d-flex align-items-center utility-cluster">
              <button class="btn btn-outline-light utility-btn ${canUndoSessionAction() ? "" : "disabled"}" type="button" id="undoTestBtn" title="Отменить последний ответ" ${canUndoSessionAction() ? "" : "disabled"}>
                <i class="bi bi-arrow-counterclockwise"></i>
              </button>
              <button class="btn ${state.lastAnswer ? "btn-light text-dark" : "btn-outline-light"}" type="button" id="testNextBtn">${state.lastAnswer ? "Следующий вопрос" : "Пропустить"}</button>
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
