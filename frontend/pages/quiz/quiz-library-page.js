(() => {
  const state = {
    user: null,
    quizzes: [],
  };

  const libraryState = document.getElementById("libraryState");
  const searchInput = document.getElementById("searchInput");
  const categoryFilter = document.getElementById("categoryFilter");
  const sortFilter = document.getElementById("sortFilter");

  function syncCategoryOptions() {
    const categories = Array.from(new Set(state.quizzes.map((quiz) => quiz.category).filter(Boolean)))
      .sort((a, b) => a.localeCompare(b));

    categoryFilter.innerHTML = `
      <option value="">All categories</option>
      ${categories.map((category) => `<option value="${quizApp.escapeHtml(category)}">${quizApp.escapeHtml(category)}</option>`).join("")}
    `;
  }

  function renderLibrary() {
    const searchValue = searchInput.value.trim().toLowerCase();
    const categoryValue = categoryFilter.value;
    const sortValue = sortFilter.value;

    let items = state.quizzes.filter((quiz) => {
      if (searchValue) {
        const haystack = `${quiz.title} ${quiz.description} ${quiz.category} ${quiz.language} ${quiz.owner_name}`.toLowerCase();
        if (!haystack.includes(searchValue)) return false;
      }
      if (categoryValue && quiz.category !== categoryValue) return false;
      return true;
    });

    if (sortValue === "title") items = items.sort((a, b) => a.title.localeCompare(b.title));
    if (sortValue === "most_played") items = items.sort((a, b) => b.attempt_count - a.attempt_count || a.title.localeCompare(b.title));
    if (sortValue === "newest") items = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    if (!items.length) {
      libraryState.innerHTML = `
        <div class="quiz-empty">
          <h2 class="h4 mb-2">No quizzes match the current filters</h2>
          <p class="mb-3">Try a broader search or create the first quiz for this topic.</p>
          <a class="btn btn-outline-light rounded-pill px-4" href="/quiz/create">Create Quiz</a>
        </div>
      `;
      return;
    }

    libraryState.innerHTML = `
      <div class="quiz-grid quiz-grid-2">
        ${items.map((quiz) => `
          <article class="quiz-card rounded-4 p-4 d-grid gap-3">
            <div class="d-flex justify-content-between gap-3">
              <div>
                <h2 class="quiz-card-title mb-2">${quizApp.escapeHtml(quiz.title)}</h2>
                <div class="text-secondary small">by ${quizApp.escapeHtml(quiz.owner_name)}</div>
              </div>
              ${quiz.can_edit ? '<span class="quiz-chip">Owner</span>' : `<span class="quiz-chip">${quiz.is_published ? "Published" : "Private draft"}</span>`}
            </div>
            <p class="text-secondary mb-0">${quizApp.escapeHtml(quiz.description || "No description provided.")}</p>
            <div class="quiz-meta">
              ${quiz.category ? quizApp.badgeHtml(quiz.category) : ""}
              ${quiz.language ? quizApp.badgeHtml(quiz.language) : ""}
            </div>
            <div class="row g-3 text-secondary small">
              <div class="col-6"><strong class="d-block text-light">${quiz.question_count}</strong>Questions</div>
              <div class="col-6"><strong class="d-block text-light">${quiz.attempt_count}</strong>Total attempts</div>
              <div class="col-6"><strong class="d-block text-light">${quizApp.formatPercent(quiz.best_attempt_percentage)}</strong>Best personal score</div>
            </div>
            <div class="d-flex flex-wrap gap-2">
              <a class="btn btn-light text-dark rounded-pill px-4" href="/quiz/${quiz.id}">Open Quiz</a>
              <a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/start">Start</a>
              ${quiz.can_edit ? `<a class="btn btn-outline-light rounded-pill px-4" href="/quiz/${quiz.id}/edit">Edit</a>` : ""}
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  async function loadLibrary() {
    const shell = await quizApp.initShell();
    state.user = shell.currentUser;
    if (!state.user) {
      quizApp.requireAuthNotice(libraryState, "Sign in to access the Quiz module", "Quiz attempts, authored content, and result history are attached to an account.");
      return;
    }
    state.quizzes = await quizApp.api("/quizzes");
    syncCategoryOptions();
    renderLibrary();
  }

  function bindEvents() {
    [searchInput, categoryFilter, sortFilter].forEach((input) => {
      input.addEventListener("input", renderLibrary);
      input.addEventListener("change", renderLibrary);
    });
  }

  function init() {
    bindEvents();
    loadLibrary().catch((error) => {
      libraryState.innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
    });
  }

  init();
})();
