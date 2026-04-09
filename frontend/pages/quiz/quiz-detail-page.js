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
    quizSubtitle.textContent = quiz.description || "Структурированный модуль проверки знаний с вручную заданными вариантами ответов.";

    detailState.innerHTML = `
      <section class="quiz-card quiz-hero rounded-4 p-4">
        <div class="d-flex flex-column flex-lg-row justify-content-between gap-4">
          <div class="d-grid gap-3">
            <div class="quiz-meta">
              ${quiz.category ? quizApp.badgeHtml(quiz.category) : ""}
              ${quiz.language ? quizApp.badgeHtml(quiz.language) : ""}
              ${quiz.is_published ? quizApp.badgeHtml("Опубликован") : quizApp.badgeHtml("Черновик")}
            </div>
            <div class="row g-3 text-secondary">
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quiz.question_count}</strong>вопросов</div>
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quizApp.formatPercent(quiz.best_attempt_percentage)}</strong>лучший результат</div>
              <div class="col-6 col-xl-3"><strong class="d-block text-light fs-4">${quizApp.formatPercent(quiz.last_attempt_percentage)}</strong>последняя попытка</div>
            </div>
            <div class="small text-secondary">Автор: ${quizApp.escapeHtml(quiz.owner_name)} • всего попыток: ${quiz.attempt_count}</div>
          </div>
          <div class="d-grid gap-2 align-content-start" style="min-width: 240px;">
            <a class="btn btn-light text-dark rounded-pill px-4" href="/quiz/${quiz.id}/start">Начать квиз</a>
            ${quiz.last_attempt_id ? `<a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/results/${quiz.last_attempt_id}">Открыть последний результат</a>` : ""}
            ${quiz.can_edit ? `<a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/edit">Редактировать квиз</a>` : ""}
          </div>
        </div>
      </section>

      <section class="quiz-grid quiz-grid-2">
        <article class="quiz-card rounded-4 p-4">
          <h2 class="h4 mb-3">Профиль проверки</h2>
          <div class="d-grid gap-3 text-secondary">
            <div>
              <div class="small text-uppercase text-secondary mb-1">Формат</div>
              <div class="text-light">Вопросы с одним правильным вариантом и вручную заданными дистракторами.</div>
            </div>
            <div>
              <div class="small text-uppercase text-secondary mb-1">Оценивание</div>
              <div class="text-light">${quiz.total_points} баллов суммарно на ${quiz.question_count} вопросов.</div>
            </div>
            ${quiz.language ? `
              <div>
                <div class="small text-uppercase text-secondary mb-1">Язык</div>
                <div class="text-light">${quizApp.escapeHtml(quiz.language)}</div>
              </div>
            ` : ""}
          </div>
        </article>

        <article class="quiz-card rounded-4 p-4">
          <h2 class="h4 mb-3">Что будет дальше</h2>
          <div class="d-grid gap-3 text-secondary">
            <div>1. При запуске квиза создаётся новая попытка.</div>
            <div>2. Ответы сохраняются, пока вы переходите между вопросами.</div>
            <div>3. В конце результаты подсчитываются и сохраняются в историю попыток.</div>
            <div>4. В режиме разбора показываются выбранный ответ, правильный ответ и объяснение.</div>
          </div>
        </article>
      </section>
    `;
  }

  loadDetail().catch((error) => {
    detailState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
  });
})();
