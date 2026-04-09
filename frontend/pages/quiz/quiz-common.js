window.quizApp = (() => {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function pluralize(count, forms) {
    const absolute = Math.abs(Number(count)) % 100;
    const lastDigit = absolute % 10;
    if (absolute > 10 && absolute < 20) return forms[2];
    if (lastDigit > 1 && lastDigit < 5) return forms[1];
    if (lastDigit === 1) return forms[0];
    return forms[2];
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    const response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      headers,
    });
    if (!response.ok) {
      let detail = "Запрос не выполнен";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (error) {
        detail = "Ошибка сервера";
      }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }

  async function logout() {
    try {
      await fetch("/logout", {
        method: "POST",
        credentials: "same-origin",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
      });
    } catch (error) {
      // Best effort logout for cookie-based auth.
    }
  }

  async function getCurrentUser() {
    try {
      return await api("/me");
    } catch (error) {
      await logout();
      return null;
    }
  }

  function initAccountMenu(currentUser) {
    const accountAvatar = document.getElementById("accountAvatar");
    const menuAvatar = document.getElementById("menuAvatar");
    const profileName = document.getElementById("profileName");
    const profileEmail = document.getElementById("profileEmail");
    const accountSummary = document.getElementById("accountSummary");
    const guestActions = document.getElementById("guestActions");
    const guestSignupWrap = document.getElementById("guestSignupWrap");
    const userActions = document.getElementById("userActions");
    const accountLoginBtn = document.getElementById("accountLoginBtn");
    const accountSignupBtn = document.getElementById("accountSignupBtn");
    const accountProfileBtn = document.getElementById("accountProfileBtn");
    const accountSettingsBtn = document.getElementById("accountSettingsBtn");
    const accountLogoutBtn = document.getElementById("accountLogoutBtn");

    const setGuestState = () => {
      if (accountAvatar) accountAvatar.textContent = "G";
      if (menuAvatar) menuAvatar.textContent = "G";
      if (profileName) profileName.textContent = "Гость";
      if (profileEmail) profileEmail.textContent = "Войдите, чтобы видеть историю квизов";
      if (accountSummary) accountSummary.classList.add("d-none");
      if (guestActions) guestActions.classList.remove("d-none");
      if (guestSignupWrap) guestSignupWrap.classList.remove("d-none");
      if (userActions) userActions.classList.add("d-none");
    };

    if (!currentUser) {
      setGuestState();
    } else {
      const shortName = currentUser.email.split("@")[0] || "Ученик";
      const initial = shortName.charAt(0).toUpperCase();
      if (accountAvatar) accountAvatar.textContent = initial;
      if (menuAvatar) menuAvatar.textContent = initial;
      if (profileName) profileName.textContent = shortName;
      if (profileEmail) profileEmail.textContent = currentUser.email;
      if (accountSummary) accountSummary.classList.remove("d-none");
      if (guestActions) guestActions.classList.add("d-none");
      if (guestSignupWrap) guestSignupWrap.classList.add("d-none");
      if (userActions) userActions.classList.remove("d-none");
    }

    if (accountLoginBtn) accountLoginBtn.onclick = () => { window.location.href = "/"; };
    if (accountSignupBtn) accountSignupBtn.onclick = () => { window.location.href = "/"; };
    if (accountProfileBtn) accountProfileBtn.onclick = () => { window.location.href = "/"; };
    if (accountSettingsBtn) accountSettingsBtn.onclick = () => { window.location.href = "/settings"; };
    if (accountLogoutBtn) {
      accountLogoutBtn.onclick = async () => {
        await logout();
        window.location.href = "/";
      };
    }
  }

  function requireAuthNotice(container, title = "Требуется вход", copy = "Этот раздел модуля квизов доступен только после авторизации.") {
    container.innerHTML = `
      <div class="quiz-empty">
        <h2 class="h4 mb-2">${escapeHtml(title)}</h2>
        <p class="mb-3">${escapeHtml(copy)}</p>
        <a class="btn btn-light text-dark rounded-pill px-4" href="/">На главную</a>
      </div>
    `;
  }

  function formatPercent(value) {
    if (value === null || value === undefined) return "Попыток ещё не было";
    return `${Math.round(value)}%`;
  }

  function badgeHtml(label, extraClass = "") {
    return `<span class="quiz-chip ${extraClass}">${escapeHtml(label)}</span>`;
  }

  async function initShell() {
    const currentUser = await getCurrentUser();
    initAccountMenu(currentUser);
    return { currentUser };
  }

  return {
    api,
    badgeHtml,
    escapeHtml,
    formatPercent,
    getCurrentUser,
    initShell,
    pluralize,
    requireAuthNotice,
  };
})();
