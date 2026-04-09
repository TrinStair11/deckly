window.appCommon = (() => {
  async function clearAuthToken() {
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

  function setAuthToken() {
    // Authentication uses an httpOnly cookie.
  }

  function getAuthToken() {
    return null;
  }

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

  async function readJsonOrText(response) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
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
        const payload = await readJsonOrText(response);
        detail = payload?.detail || detail;
      } catch (error) {
        detail = "Ошибка сервера";
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
      await clearAuthToken();
      return null;
    }
  }

  function renderAccountMenu(user, refs, options = {}) {
    const guestName = options.guestName || "Гость";
    const guestEmail = options.guestEmail || "Войдите через меню";
    const userNameFallback = options.userNameFallback || "Ученик";
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
          guestEmail: guestEmail || "Войдите через меню",
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
    pluralize,
    renderAccountMenu,
    setAuthToken,
  };
})();
