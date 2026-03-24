window.quizApp = (() => {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function api(path, options = {}) {
    const token = localStorage.getItem("token");
    const headers = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      let detail = "Request failed";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (error) {
        detail = "Server error";
      }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }

  async function getCurrentUser() {
    try {
      return await api("/me");
    } catch (error) {
      localStorage.removeItem("token");
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
      if (profileName) profileName.textContent = "Guest";
      if (profileEmail) profileEmail.textContent = "Sign in to access quiz history";
      if (accountSummary) accountSummary.classList.add("d-none");
      if (guestActions) guestActions.classList.remove("d-none");
      if (guestSignupWrap) guestSignupWrap.classList.remove("d-none");
      if (userActions) userActions.classList.add("d-none");
    };

    if (!currentUser) {
      setGuestState();
    } else {
      const shortName = currentUser.email.split("@")[0] || "Learner";
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
    if (accountSettingsBtn) accountSettingsBtn.onclick = () => { window.location.href = "/settings.html"; };
    if (accountLogoutBtn) {
      accountLogoutBtn.onclick = () => {
        localStorage.removeItem("token");
        window.location.href = "/";
      };
    }
  }

  function requireAuthNotice(container, title = "Sign in required", copy = "This part of the Quiz module is available after authentication.") {
    container.innerHTML = `
      <div class="quiz-empty">
        <h2 class="h4 mb-2">${escapeHtml(title)}</h2>
        <p class="mb-3">${escapeHtml(copy)}</p>
        <a class="btn btn-light text-dark rounded-pill px-4" href="/">Go to Home</a>
      </div>
    `;
  }

  function formatDifficulty(value) {
    if (!value) return "Unspecified";
    return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function difficultyClass(value) {
    return `difficulty-${(value || "beginner").toLowerCase()}`;
  }

  function formatTime(minutes) {
    if (!minutes) return "Flexible";
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours}h ${rest}m` : `${hours}h`;
  }

  function formatPercent(value) {
    if (value === null || value === undefined) return "No attempts yet";
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
    difficultyClass,
    escapeHtml,
    formatDifficulty,
    formatPercent,
    formatTime,
    getCurrentUser,
    initShell,
    requireAuthNotice,
  };
})();
