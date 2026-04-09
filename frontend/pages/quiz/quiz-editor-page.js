(() => {
  const pathSegments = window.location.pathname.split("/").filter(Boolean);
  const isCreateMode = pathSegments[1] === "create";
  const quizId = isCreateMode ? null : pathSegments[1];

  const questionsList = document.getElementById("questionsList");
  const editorTitle = document.getElementById("editorTitle");
  const editorSubtitle = document.getElementById("editorSubtitle");
  const editorBackLink = document.getElementById("editorBackLink");
  const deleteWrap = document.getElementById("deleteWrap");
  const editorFeedback = document.getElementById("editorFeedback");
  const saveButtons = [
    document.getElementById("saveQuizBtn"),
    document.getElementById("saveQuizBtnBottom"),
  ];

  const form = {
    titleInput: document.getElementById("titleInput"),
    descriptionInput: document.getElementById("descriptionInput"),
    categoryInput: document.getElementById("categoryInput"),
    languageInput: document.getElementById("languageInput"),
    coverImageInput: document.getElementById("coverImageInput"),
    tagsInput: document.getElementById("tagsInput"),
    publishedInput: document.getElementById("publishedInput"),
  };

  const state = {
    quizMeta: {
      difficulty: "beginner",
      subject: "",
      estimated_time: null,
    },
    questions: [],
  };

  function setEditorFeedback(message = "", type = "danger") {
    editorFeedback.textContent = message;
    editorFeedback.className = `small text-${type}${message ? "" : " d-none"}`;
  }

  function setSaveState(isSaving) {
    saveButtons.forEach((button) => {
      button.disabled = isSaving;
      button.textContent = isSaving ? "Сохранение..." : "Сохранить квиз";
    });
  }

  function makeOption(option = {}) {
    return {
      id: option.id || null,
      option_text: option.option_text || "",
      is_correct: Boolean(option.is_correct),
      order_index: option.order_index ?? 0,
    };
  }

  function makeQuestion(question = {}) {
    const options = (question.options || [makeOption({ is_correct: true }), makeOption()]).map(makeOption);
    let foundCorrect = false;
    const normalizedOptions = options.map((option, index) => {
      const isCorrect = Boolean(option.is_correct) && !foundCorrect;
      if (isCorrect) foundCorrect = true;
      return {
        ...option,
        order_index: option.order_index ?? index,
        is_correct: isCorrect,
      };
    });
    if (!foundCorrect && normalizedOptions[0]) {
      normalizedOptions[0] = { ...normalizedOptions[0], is_correct: true };
    }

    return {
      id: question.id || null,
      question_text: question.question_text || "",
      question_type: "single_choice",
      explanation: question.explanation || "",
      order_index: question.order_index ?? state.questions.length,
      points: question.points || 1,
      options: normalizedOptions,
    };
  }

  function renderQuestions() {
    if (!state.questions.length) {
      questionsList.innerHTML = '<div class="quiz-empty">Вопросов пока нет. Добавьте первый, чтобы квиз можно было запустить.</div>';
      return;
    }

    questionsList.innerHTML = state.questions.map((question, questionIndex) => `
      <article class="quiz-editor-question p-3" data-question-index="${questionIndex}">
        <div class="d-flex justify-content-between align-items-center gap-2 mb-3 flex-wrap">
          <div class="small text-uppercase text-secondary">Вопрос ${questionIndex + 1}</div>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-danger rounded-pill" type="button" data-action="remove-question">Удалить</button>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-12">
            <label class="form-label">Текст вопроса</label>
            <textarea class="form-control quiz-textarea" data-field="question_text" rows="2" placeholder="Введите вопрос">${quizApp.escapeHtml(question.question_text)}</textarea>
          </div>
          <div class="col-12 col-xl-3">
            <label class="form-label">Тип</label>
            <select class="form-select quiz-select" data-field="question_type">
              <option value="single_choice" ${question.question_type === "single_choice" ? "selected" : ""}>Один вариант ответа</option>
            </select>
          </div>
          <div class="col-12 col-xl-2">
            <label class="form-label">Баллы</label>
            <input class="form-control quiz-input" data-field="points" type="number" min="1" max="100" value="${question.points}" />
          </div>
          <div class="col-12 col-xl-7">
            <label class="form-label">Пояснение</label>
            <input class="form-control quiz-input" data-field="explanation" type="text" maxlength="2000" value="${quizApp.escapeHtml(question.explanation)}" placeholder="Показывается в режиме разбора" />
          </div>
        </div>
        <div class="mt-3 d-grid gap-2">
          ${question.options.map((option, optionIndex) => `
            <div class="quiz-card rounded-4 p-3" data-option-index="${optionIndex}">
              <div class="row g-3 align-items-center">
                <div class="col-12 col-xl-1 text-secondary small">${String.fromCharCode(65 + optionIndex)}</div>
                <div class="col-12 col-xl-7">
                  <input class="form-control quiz-input" data-option-field="option_text" type="text" maxlength="500" value="${quizApp.escapeHtml(option.option_text)}" placeholder="Вариант ответа" />
                </div>
                <div class="col-12 col-xl-2">
                  <div class="form-check">
                    <input class="form-check-input" data-option-field="is_correct" type="radio" name="correct-option-${questionIndex}" ${option.is_correct ? "checked" : ""} />
                    <label class="form-check-label">Правильный</label>
                  </div>
                </div>
                <div class="col-12 col-xl-2 d-flex gap-2 justify-content-xl-end">
                  <button class="btn btn-sm btn-outline-danger rounded-pill" type="button" data-action="remove-option" ${question.options.length <= 2 ? "disabled" : ""}>Убрать</button>
                </div>
              </div>
            </div>
          `).join("")}
          <div>
            <button class="btn btn-outline-light rounded-pill px-4" type="button" data-action="add-option">Добавить вариант</button>
          </div>
        </div>
      </article>
    `).join("");
  }

  function bindQuestionEvents() {
    document.querySelectorAll("[data-question-index]").forEach((questionNode) => {
      const questionIndex = Number(questionNode.dataset.questionIndex);

      questionNode.querySelectorAll("[data-field]").forEach((field) => {
        field.addEventListener("input", () => {
          const key = field.dataset.field;
          state.questions[questionIndex][key] = key === "points" ? Number(field.value || 1) : field.value;
        });
        field.addEventListener("change", () => {
          const key = field.dataset.field;
          state.questions[questionIndex][key] = key === "points" ? Number(field.value || 1) : field.value;
          if (key === "question_type") {
            let foundCorrect = false;
            state.questions[questionIndex].options = state.questions[questionIndex].options.map((option) => {
              if (option.is_correct && !foundCorrect) {
                foundCorrect = true;
                return option;
              }
              return { ...option, is_correct: false };
            });
            renderQuestions();
            bindQuestionEvents();
          }
        });
      });

      questionNode.querySelectorAll("[data-option-index]").forEach((optionNode) => {
        const optionIndex = Number(optionNode.dataset.optionIndex);
        const optionTextInput = optionNode.querySelector('[data-option-field="option_text"]');
        const optionCorrectInput = optionNode.querySelector('[data-option-field="is_correct"]');

        optionTextInput.addEventListener("input", () => {
          state.questions[questionIndex].options[optionIndex].option_text = optionTextInput.value;
        });
        optionCorrectInput.addEventListener("change", () => {
          const question = state.questions[questionIndex];
          question.options = question.options.map((option, currentIndex) => ({ ...option, is_correct: currentIndex === optionIndex }));
          renderQuestions();
          bindQuestionEvents();
        });

        optionNode.querySelectorAll("[data-action]").forEach((button) => {
          button.addEventListener("click", () => {
            const question = state.questions[questionIndex];
            if (button.dataset.action === "remove-option" && question.options.length > 2) {
              question.options.splice(optionIndex, 1);
            }
            renderQuestions();
            bindQuestionEvents();
          });
        });
      });

      questionNode.querySelectorAll(":scope > .d-flex [data-action], :scope .mt-3 > div [data-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.dataset.action === "remove-question") state.questions.splice(questionIndex, 1);
          if (button.dataset.action === "add-option") {
            state.questions[questionIndex].options.push(makeOption());
          }
          renderQuestions();
          bindQuestionEvents();
        });
      });
    });
  }

  function buildPayload() {
    return {
      title: form.titleInput.value.trim(),
      description: form.descriptionInput.value.trim(),
      category: form.categoryInput.value.trim(),
      difficulty: state.quizMeta.difficulty,
      subject: state.quizMeta.subject,
      language: form.languageInput.value.trim(),
      is_published: form.publishedInput.checked,
      cover_image: form.coverImageInput.value.trim(),
      estimated_time: state.quizMeta.estimated_time,
      tags: form.tagsInput.value.split(",").map((tag) => tag.trim()).filter(Boolean),
      questions: state.questions.map((question, questionIndex) => ({
        id: question.id || null,
        question_text: question.question_text.trim(),
        question_type: question.question_type,
        explanation: question.explanation.trim(),
        order_index: questionIndex,
        points: Number(question.points || 1),
        options: question.options.map((option, optionIndex) => ({
          id: option.id || null,
          option_text: option.option_text.trim(),
          is_correct: Boolean(option.is_correct),
          order_index: optionIndex,
        })),
      })),
    };
  }

  async function saveQuiz() {
    setEditorFeedback("");
    setSaveState(true);
    const payload = buildPayload();
    const method = isCreateMode ? "POST" : "PUT";
    const path = isCreateMode ? "/quizzes" : `/quizzes/${quizId}`;

    try {
      const response = await quizApp.api(path, { method, body: JSON.stringify(payload) });
      window.location.href = `/quiz/${response.id}`;
    } catch (error) {
      setEditorFeedback(error.message || "Не удалось сохранить квиз.");
    } finally {
      setSaveState(false);
    }
  }

  async function loadEditor() {
    const shell = await quizApp.initShell();
    if (!shell.currentUser) {
      quizApp.requireAuthNotice(document.getElementById("editorState"));
      return;
    }

    if (!isCreateMode) {
      const quiz = await quizApp.api(`/quizzes/${quizId}/edit-data`);
      editorTitle.textContent = "Редактирование квиза";
      editorSubtitle.textContent = "Обновляйте метаданные квиза, управляйте вариантами ответов и сохраняйте порядок вопросов.";
      editorBackLink.href = `/quiz/${quizId}`;
      form.titleInput.value = quiz.title;
      form.descriptionInput.value = quiz.description;
      form.categoryInput.value = quiz.category;
      form.languageInput.value = quiz.language;
      form.coverImageInput.value = quiz.cover_image;
      form.tagsInput.value = (quiz.tags || []).join(", ");
      form.publishedInput.checked = quiz.is_published;
      state.quizMeta.difficulty = quiz.difficulty || "beginner";
      state.quizMeta.subject = quiz.subject || "";
      state.quizMeta.estimated_time = quiz.estimated_time || null;
      state.questions = quiz.questions.map(makeQuestion);
      deleteWrap.innerHTML = '<button class="btn btn-outline-danger rounded-pill px-4" type="button" id="deleteQuizBtn">Удалить квиз</button>';
      document.getElementById("deleteQuizBtn").addEventListener("click", async () => {
        const confirmed = window.confirm("Удалить этот квиз?");
        if (!confirmed) return;
        await quizApp.api(`/quizzes/${quizId}`, { method: "DELETE" });
        window.location.href = "/quiz";
      });
    } else {
      state.quizMeta = {
        difficulty: "beginner",
        subject: "",
        estimated_time: null,
      };
      state.questions = [];
    }

    renderQuestions();
    bindQuestionEvents();
  }

  function bindEvents() {
    document.getElementById("addQuestionBtn").addEventListener("click", () => {
      state.questions.push(makeQuestion({ options: [makeOption({ is_correct: true }), makeOption()] }));
      renderQuestions();
      bindQuestionEvents();
    });
    document.getElementById("saveQuizBtn").addEventListener("click", saveQuiz);
    document.getElementById("saveQuizBtnBottom").addEventListener("click", saveQuiz);
  }

  function init() {
    bindEvents();
    loadEditor().catch((error) => {
      document.getElementById("editorState").innerHTML = `<div class="quiz-empty text-danger">${quizApp.escapeHtml(error.message)}</div>`;
    });
  }

  init();
})();
