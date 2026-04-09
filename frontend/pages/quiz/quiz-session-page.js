(() => {
  const pathSegments = window.location.pathname.split("/").filter(Boolean);
  const quizId = pathSegments[1];
  const attemptStorageKey = `quiz-attempt:${quizId}`;

  const state = {
    currentIndex: 0,
    attempt: null,
  };

  const sessionState = document.getElementById("sessionState");
  const sessionTitle = document.getElementById("sessionTitle");
  const sessionSubtitle = document.getElementById("sessionSubtitle");
  const backToQuizLink = document.getElementById("backToQuizLink");

  function currentQuestion() {
    return state.attempt?.questions?.[state.currentIndex] || null;
  }

  function renderSession() {
    const question = currentQuestion();
    if (!state.attempt || !question) {
      sessionState.innerHTML = '<div class="quiz-empty">Не удалось загрузить попытку квиза.</div>';
      return;
    }

    const progress = state.attempt.total_questions ? ((state.currentIndex + 1) / state.attempt.total_questions) * 100 : 0;
    sessionTitle.textContent = state.attempt.quiz_title;
    sessionSubtitle.textContent = "Выберите один ответ и переходите к следующему вопросу.";
    backToQuizLink.href = `/quiz/${state.attempt.quiz_id}`;

    sessionState.innerHTML = `
      <section class="quiz-card rounded-4 p-4 quiz-session-stage">
        <div class="quiz-question-progress mb-4">
          <div class="d-flex justify-content-between align-items-end gap-3 mb-2 flex-wrap">
            <div>
              <div class="small text-uppercase text-secondary">Прогресс</div>
              <div class="quiz-question-progress-count">${state.currentIndex + 1} / ${state.attempt.total_questions}</div>
            </div>
            <div class="quiz-question-progress-note">
              ${question.selected_option_id === null ? "Выберите лучший вариант, чтобы продолжить." : "Ответ выбран. Продолжайте, когда будете готовы."}
            </div>
          </div>
          <div class="quiz-progress">
            <div class="quiz-progress-bar" style="width:${progress.toFixed(2)}%"></div>
          </div>
        </div>
        <article class="quiz-card quiz-question-card rounded-4 p-4">
          <div class="quiz-question-body">
            <div class="quiz-question-kicker">Вопрос</div>
            <h2 class="quiz-question-title mt-2 mb-4">${quizApp.escapeHtml(question.question_text)}</h2>
            <div class="quiz-question-options">
              ${question.options.map((option, optionIndex) => `
                <button class="quiz-option ${question.selected_option_id === option.id ? "selected" : ""}" type="button" data-option-id="${option.id}">
                  <span class="quiz-option-content">
                    <span class="quiz-option-letter fw-semibold">${String.fromCharCode(65 + optionIndex)}</span>
                    <span class="quiz-option-text">${quizApp.escapeHtml(option.option_text)}</span>
                  </span>
                </button>
              `).join("")}
            </div>
          </div>
          <div class="quiz-question-actions">
            <button class="btn btn-outline-light rounded-pill px-4" type="button" id="prevQuestionBtn" ${state.currentIndex === 0 ? "disabled" : ""}>Назад</button>
            <div class="d-flex gap-2 flex-wrap justify-content-end">
              <button class="btn btn-outline-danger rounded-pill px-4" type="button" id="finishQuizBtn">Завершить квиз</button>
              <button class="btn btn-light text-dark rounded-pill px-4 quiz-next-btn" type="button" id="nextQuestionBtn" ${question.selected_option_id === null ? "disabled" : ""}>
                ${state.currentIndex === state.attempt.total_questions - 1 ? "Отправить квиз" : "Следующий вопрос"}
              </button>
            </div>
          </div>
        </article>
      </section>
    `;

    document.querySelectorAll("[data-option-id]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const nextState = await quizApp.api(`/quiz-attempts/${state.attempt.id}/answers/${question.id}`, {
            method: "PUT",
            body: JSON.stringify({ selected_option_id: Number(button.dataset.optionId) }),
          });
          state.attempt = nextState;
          renderSession();
        } catch (error) {
          window.alert(error.message);
        }
      });
    });

    document.getElementById("prevQuestionBtn").addEventListener("click", () => {
      state.currentIndex = Math.max(state.currentIndex - 1, 0);
      renderSession();
    });
    document.getElementById("finishQuizBtn").addEventListener("click", async () => {
      const remaining = Math.max(state.attempt.total_questions - state.attempt.answered_count, 0);
      const shouldFinish = remaining > 0
        ? window.confirm(`Завершить квиз сейчас? ${remaining} ${quizApp.pluralize(remaining, ["вопрос", "вопроса", "вопросов"])} будет отмечено без ответа.`)
        : window.confirm("Завершить квиз сейчас?");
      if (!shouldFinish) return;
      const result = await quizApp.api(`/quiz-attempts/${state.attempt.id}/complete`, { method: "POST" });
      sessionStorage.removeItem(attemptStorageKey);
      window.location.href = `/quiz/${state.attempt.quiz_id}/results/${result.id}`;
    });
    document.getElementById("nextQuestionBtn").addEventListener("click", async () => {
      if (state.currentIndex === state.attempt.total_questions - 1) {
        const result = await quizApp.api(`/quiz-attempts/${state.attempt.id}/complete`, { method: "POST" });
        sessionStorage.removeItem(attemptStorageKey);
        window.location.href = `/quiz/${state.attempt.quiz_id}/results/${result.id}`;
        return;
      }
      state.currentIndex = Math.min(state.currentIndex + 1, state.attempt.total_questions - 1);
      renderSession();
    });
  }

  async function hydrateAttempt() {
    const storedAttemptId = sessionStorage.getItem(attemptStorageKey);
    if (storedAttemptId) {
      try {
        const attempt = await quizApp.api(`/quiz-attempts/${storedAttemptId}`);
        if (attempt.status === "in_progress") {
          state.attempt = attempt;
          state.currentIndex = attempt.current_question_index || 0;
          return;
        }
      } catch (error) {
        sessionStorage.removeItem(attemptStorageKey);
      }
    }

    const attempt = await quizApp.api(`/quizzes/${quizId}/start`, { method: "POST" });
    state.attempt = attempt;
    state.currentIndex = attempt.current_question_index || 0;
    sessionStorage.setItem(attemptStorageKey, String(attempt.id));
  }

  async function boot() {
    const shell = await quizApp.initShell();
    if (!shell.currentUser) {
      quizApp.requireAuthNotice(sessionState, "Войдите, чтобы проходить квизы", "Попытки, результаты и история разбора сохраняются отдельно для каждого аккаунта.");
      return;
    }
    await hydrateAttempt();
    renderSession();
  }

  boot().catch((error) => {
    sessionState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
  });
})();
