(() => {
  const pathSegments = window.location.pathname.split("/").filter(Boolean);
  const quizId = pathSegments[1];
  const attemptId = pathSegments[3];
  const resultsState = document.getElementById("resultsState");
  const backToQuizLink = document.getElementById("backToQuizLink");

  function performanceClass(percentage) {
    if (percentage >= 80) return "performance-high";
    if (percentage >= 50) return "performance-medium";
    return "performance-low";
  }

  function resultMessage(result) {
    if (result.percentage >= 85) return "Strong result. You handled this quiz with confidence.";
    if (result.percentage >= 60) return "Solid pass. A quick review will lock in the weaker parts.";
    return "You finished the quiz. Review the missed answers and run it again once more.";
  }

  async function loadResults() {
    const shell = await quizApp.initShell();
    if (!shell.currentUser) {
      quizApp.requireAuthNotice(resultsState);
      return;
    }

    const result = await quizApp.api(`/quiz-attempts/${attemptId}/results`);
    backToQuizLink.href = `/quiz/${quizId}`;
    const score = Math.round(result.percentage);
    const toneClass = performanceClass(result.percentage);
    const timeValue = result.completion_time_seconds || 0;

    resultsState.innerHTML = `
      <section class="quiz-results-stage">
        <article class="quiz-card quiz-results-card rounded-4 ${toneClass}">
          <div class="quiz-results-kicker">Completed</div>
          <div class="quiz-score-wrap">
            <div class="quiz-score-label">Your score</div>
            <div class="quiz-score-value">${score}%</div>
          </div>
          <div class="mt-3">
            <h2 class="quiz-results-title">${quizApp.escapeHtml(result.quiz_title)}</h2>
            <p class="quiz-results-summary">${result.correct_count} correct, ${result.wrong_count} wrong. ${quizApp.escapeHtml(resultMessage(result))}</p>
          </div>
          <div class="quiz-results-meta">
            <div class="quiz-results-stat">
              <div class="quiz-results-stat-label">Correct</div>
              <span class="quiz-results-stat-value is-correct">${result.correct_count}</span>
            </div>
            <div class="quiz-results-stat">
              <div class="quiz-results-stat-label">Wrong</div>
              <span class="quiz-results-stat-value is-wrong">${result.wrong_count}</span>
            </div>
            <div class="quiz-results-stat">
              <div class="quiz-results-stat-label">Reviewed</div>
              <span class="quiz-results-stat-value">${result.total_questions}</span>
            </div>
          </div>
          <div class="quiz-results-time">Completed in ${timeValue}s</div>
          <div class="quiz-results-actions">
            <a class="btn btn-light text-dark rounded-pill px-4" href="/quiz/${quizId}/results/${attemptId}/review">Review answers</a>
            <a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quizId}/start">Restart quiz</a>
            <a class="quiz-tertiary-link" href="/quiz/${quizId}"><i class="bi bi-arrow-left"></i><span>Back to details</span></a>
          </div>
        </article>
      </section>
    `;
  }

  loadResults().catch((error) => {
    resultsState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
  });
})();
