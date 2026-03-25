(() => {
  const pathSegments = window.location.pathname.split("/").filter(Boolean);
  const quizId = pathSegments[1];
  const attemptId = pathSegments[3];
  const reviewState = document.getElementById("reviewState");
  const backToResultsLink = document.getElementById("backToResultsLink");

  async function loadReview() {
    const shell = await quizApp.initShell();
    if (!shell.currentUser) {
      quizApp.requireAuthNotice(reviewState);
      return;
    }

    const result = await quizApp.api(`/quiz-attempts/${attemptId}/results`);
    backToResultsLink.href = `/quiz/${quizId}/results/${attemptId}`;

    reviewState.innerHTML = `
      ${result.review_items.map((item, index) => `
        <article class="quiz-card rounded-4 p-4 d-grid gap-3">
          <div class="d-flex justify-content-between gap-3 flex-wrap">
            <div>
              <div class="small text-uppercase text-secondary mb-2">Question ${index + 1}</div>
              <h2 class="h4 mb-0">${quizApp.escapeHtml(item.question_text)}</h2>
            </div>
            <span class="quiz-chip ${item.is_correct ? "difficulty-beginner" : "difficulty-advanced"}">${item.is_correct ? "Correct" : "Incorrect"}</span>
          </div>
          <div class="row g-3">
            <div class="col-12 col-xl-6">
              <div class="small text-uppercase text-secondary mb-2">Your answer</div>
              <div class="quiz-card rounded-4 p-3">${quizApp.escapeHtml(item.selected_option_text || "No answer submitted")}</div>
            </div>
            <div class="col-12 col-xl-6">
              <div class="small text-uppercase text-secondary mb-2">Correct answer</div>
              <div class="quiz-card rounded-4 p-3 border-success-subtle">${quizApp.escapeHtml(item.correct_option_text)}</div>
            </div>
          </div>
          <div>
            <div class="small text-uppercase text-secondary mb-2">Explanation</div>
            <div class="text-secondary">${quizApp.escapeHtml(item.explanation || "No explanation provided.")}</div>
          </div>
        </article>
      `).join("")}
    `;
  }

  loadReview().catch((error) => {
    reviewState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
  });
})();
