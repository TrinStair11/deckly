(() => {
  const quizId = window.location.pathname.split("/").filter(Boolean).at(-1);
  const detailState = document.getElementById("detailState");
  const quizTitle = document.getElementById("quizTitle");
  const quizSubtitle = document.getElementById("quizSubtitle");

  async function loadDetail() {
    const shell = await quizApp.initShell();
    if (!shell.currentUser) {
      quizApp.requireAuthNotice(detailState);
      return;
    }

    const quiz = await quizApp.api(`/quizzes/${quizId}`);
    quizTitle.textContent = quiz.title;
    quizSubtitle.textContent = quiz.description || "A structured assessment module with manually authored answer options.";

    detailState.innerHTML = `
      <section class="quiz-card quiz-hero rounded-4 p-4">
        <div class="d-flex flex-column flex-lg-row justify-content-between gap-4">
          <div class="d-grid gap-3">
            <div class="quiz-meta">
              ${quiz.category ? quizApp.badgeHtml(quiz.category) : ""}
              ${quiz.language ? quizApp.badgeHtml(quiz.language) : ""}
              ${quiz.is_published ? quizApp.badgeHtml("Published") : quizApp.badgeHtml("Draft")}
            </div>
            <div class="row g-3 text-secondary">
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quiz.question_count}</strong>questions</div>
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quizApp.formatPercent(quiz.best_attempt_percentage)}</strong>best result</div>
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quizApp.formatPercent(quiz.last_attempt_percentage)}</strong>last attempt</div>
            </div>
            <div class="small text-secondary">Created by ${quizApp.escapeHtml(quiz.owner_name)} • ${quiz.attempt_count} total attempt${quiz.attempt_count === 1 ? "" : "s"}</div>
          </div>
          <div class="d-grid gap-2 align-content-start" style="min-width: 240px;">
            <a class="btn btn-light text-dark rounded-pill px-4" href="/quiz/${quiz.id}/start">Start Quiz</a>
            ${quiz.last_attempt_id ? `<a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/results/${quiz.last_attempt_id}">Open Last Result</a>` : ""}
            ${quiz.can_edit ? `<a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/edit">Edit Quiz</a>` : ""}
          </div>
        </div>
      </section>

      <section class="quiz-grid quiz-grid-2">
        <article class="quiz-card rounded-4 p-4">
          <h2 class="h4 mb-3">Assessment profile</h2>
          <div class="d-grid gap-3 text-secondary">
            <div>
              <div class="small text-uppercase text-secondary mb-1">Format</div>
              <div class="text-light">Single-choice questions with manually authored distractors.</div>
            </div>
            <div>
              <div class="small text-uppercase text-secondary mb-1">Scoring</div>
              <div class="text-light">${quiz.total_points} total point${quiz.total_points === 1 ? "" : "s"} across ${quiz.question_count} question${quiz.question_count === 1 ? "" : "s"}.</div>
            </div>
            ${quiz.language ? `
              <div>
                <div class="small text-uppercase text-secondary mb-1">Language</div>
                <div class="text-light">${quizApp.escapeHtml(quiz.language)}</div>
              </div>
            ` : ""}
          </div>
        </article>

        <article class="quiz-card rounded-4 p-4">
          <h2 class="h4 mb-3">What happens next</h2>
          <div class="d-grid gap-3 text-secondary">
            <div>1. A new attempt is created when you start the quiz.</div>
            <div>2. Answers persist while you move between questions.</div>
            <div>3. Results are scored at the end and saved to your attempt history.</div>
            <div>4. Review mode shows the selected answer, correct answer, and explanation.</div>
          </div>
        </article>
      </section>
    `;
  }

  loadDetail().catch((error) => {
    detailState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
  });
})();
