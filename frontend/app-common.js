window.appCommon = (() => {
  function clearAuthToken() {
    localStorage.removeItem("token");
  }

  function setAuthToken(token) {
    localStorage.setItem("token", token);
  }

  function getAuthToken() {
    return localStorage.getItem("token");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function readJsonOrText(response) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }

  async function api(path, options = {}) {
    const token = getAuthToken();
    const headers = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      let detail = "Request failed";
      try {
        const payload = await readJsonOrText(response);
        detail = payload?.detail || detail;
      } catch (error) {
        detail = "Server error";
      }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return readJsonOrText(response);
  }

  async function getCurrentUser(apiClient = api) {
    try {
      return await apiClient("/me");
    } catch (error) {
      clearAuthToken();
      return null;
    }
  }

  function renderAccountMenu(user, refs, options = {}) {
    const guestName = options.guestName || "Guest";
    const guestEmail = options.guestEmail || "Use the menu to sign in";
    const userNameFallback = options.userNameFallback || "Learner";
    const userName = user?.email?.split("@")[0] || userNameFallback;
    const initial = (userName || guestName).charAt(0).toUpperCase() || "G";

    if (refs.accountAvatar) refs.accountAvatar.textContent = user ? initial : "G";
    if (refs.menuAvatar) refs.menuAvatar.textContent = user ? initial : "G";
    if (refs.profileName) refs.profileName.textContent = user ? userName : guestName;
    if (refs.profileEmail) refs.profileEmail.textContent = user ? user.email : guestEmail;
    if (refs.accountSummary) refs.accountSummary.classList.toggle("d-none", !user);
    if (refs.guestActions) refs.guestActions.classList.toggle("d-none", Boolean(user));
    if (refs.guestSignupWrap) refs.guestSignupWrap.classList.toggle("d-none", Boolean(user));
    if (refs.userActions) refs.userActions.classList.toggle("d-none", !user);
  }

  function bindHandler(node, handler) {
    if (!node || !handler) return;
    node.addEventListener("click", (event) => {
      event.preventDefault();
      handler(event);
    });
  }

  function initAccountMenu({ refs, onLogin, onSignup, onProfile, onSettings, onLogout, guestEmail } = {}) {
    bindHandler(refs.accountLoginBtn, onLogin);
    bindHandler(refs.accountSignupBtn, onSignup);
    bindHandler(refs.accountProfileBtn, onProfile);
    bindHandler(refs.accountSettingsBtn, onSettings);
    bindHandler(refs.accountLogoutBtn, onLogout);

    return {
      render(user, extraOptions = {}) {
        renderAccountMenu(user, refs, {
          guestEmail: guestEmail || "Use the menu to sign in",
          ...extraOptions,
        });
      },
    };
  }

  return {
    api,
    clearAuthToken,
    escapeHtml,
    getAuthToken,
    getCurrentUser,
    initAccountMenu,
    renderAccountMenu,
    setAuthToken,
  };
})();
