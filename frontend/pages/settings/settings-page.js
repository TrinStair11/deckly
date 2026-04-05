(() => {
  const { renderSidebar, renderAccountMenu, getAccountMenuRefs } = window.appShell;
  const { api, clearAuthToken, getCurrentUser, initAccountMenu } = window.appCommon;
  const { getAuthModalRefs, initAuthModal } = window.appAuth;

  renderSidebar(document.getElementById("sidebarShell"), {
    active: "settings",
    decksHref: "/#decksSection",
  });
  renderAccountMenu(document.getElementById("accountMenuSlot"), {
    menuClass: "dropdown-menu dropdown-menu-end shadow-sm rounded-4 p-2",
  });

  const state = {
    me: null,
    emailSaving: false,
    passwordSaving: false,
  };

  const accountRefs = getAccountMenuRefs();
  const dom = {
    guestSettingsState: document.getElementById("guestSettingsState"),
    accountForms: document.getElementById("accountForms"),
    currentEmailInput: document.getElementById("currentEmailInput"),
    newEmailInput: document.getElementById("newEmailInput"),
    confirmEmailInput: document.getElementById("confirmEmailInput"),
    emailCurrentPasswordInput: document.getElementById("emailCurrentPasswordInput"),
    changeEmailBtn: document.getElementById("changeEmailBtn"),
    emailStatus: document.getElementById("emailStatus"),
    emailForm: document.getElementById("emailForm"),
    currentPasswordInput: document.getElementById("currentPasswordInput"),
    newPasswordInput: document.getElementById("newPasswordInput"),
    confirmPasswordInput: document.getElementById("confirmPasswordInput"),
    changePasswordBtn: document.getElementById("changePasswordBtn"),
    passwordStatus: document.getElementById("passwordStatus"),
    passwordForm: document.getElementById("passwordForm"),
  };

  const authRefs = getAuthModalRefs({ emailId: "authEmail", passwordId: "authPassword" });

  function setStatus(node, message, type) {
    if (!node) return;
    node.textContent = message || "";
    node.className = "status-line";
    if (!message) return;
    if (type === "success") node.classList.add("text-success");
    if (type === "error") node.classList.add("text-danger");
    if (!type) node.classList.add("text-secondary");
  }

  const authUi = initAuthModal({
    refs: authRefs,
    setStatus,
    onAuthenticated: loadProfile,
  });

  const accountMenuUi = initAccountMenu({
    refs: accountRefs,
    onLogin: authUi.openLogin,
    onSignup: authUi.openSignup,
    onProfile: () => {
      window.location.href = "/";
    },
    onSettings: () => {
      window.location.href = "/settings";
    },
    onLogout: logout,
  });

  function renderProfile() {
    accountMenuUi.render(state.me);
  }

  function renderAccountSettings() {
    const isLoggedIn = Boolean(state.me);
    dom.guestSettingsState.classList.toggle("d-none", isLoggedIn);
    dom.accountForms.classList.toggle("d-none", !isLoggedIn);

    if (isLoggedIn) {
      dom.currentEmailInput.value = state.me.email;
    } else {
      dom.currentEmailInput.value = "";
      dom.newEmailInput.value = "";
      dom.confirmEmailInput.value = "";
      dom.emailCurrentPasswordInput.value = "";
      dom.currentPasswordInput.value = "";
      dom.newPasswordInput.value = "";
      dom.confirmPasswordInput.value = "";
    }

    setStatus(dom.emailStatus, "", "");
    setStatus(dom.passwordStatus, "", "");
  }

  async function loadProfile() {
    state.me = await getCurrentUser(api);
    renderProfile();
    renderAccountSettings();
  }

  async function submitEmailUpdate(event) {
    event.preventDefault();
    if (!state.me) {
      setStatus(dom.emailStatus, "Log in first.", "error");
      return;
    }

    const newEmail = dom.newEmailInput.value.trim().toLowerCase();
    const confirmEmail = dom.confirmEmailInput.value.trim().toLowerCase();
    const currentPassword = dom.emailCurrentPasswordInput.value.trim();

    if (!newEmail || !confirmEmail || !currentPassword) {
      setStatus(dom.emailStatus, "Fill all fields.", "error");
      return;
    }
    if (newEmail !== confirmEmail) {
      setStatus(dom.emailStatus, "Email confirmation does not match.", "error");
      return;
    }
    if (newEmail === state.me.email) {
      setStatus(dom.emailStatus, "New email must be different from current email.", "error");
      return;
    }

    state.emailSaving = true;
    dom.changeEmailBtn.disabled = true;
    setStatus(dom.emailStatus, "Updating email...", "");
    try {
      const updatedUser = await api("/account/email", {
        method: "PUT",
        body: JSON.stringify({
          new_email: newEmail,
          confirm_email: confirmEmail,
          current_password: currentPassword,
        }),
      });
      state.me = updatedUser;
      renderProfile();
      renderAccountSettings();
      dom.newEmailInput.value = "";
      dom.confirmEmailInput.value = "";
      dom.emailCurrentPasswordInput.value = "";
      setStatus(dom.emailStatus, "Email updated successfully.", "success");
    } catch (error) {
      setStatus(dom.emailStatus, error.message, "error");
    } finally {
      state.emailSaving = false;
      dom.changeEmailBtn.disabled = false;
    }
  }

  async function submitPasswordUpdate(event) {
    event.preventDefault();
    if (!state.me) {
      setStatus(dom.passwordStatus, "Log in first.", "error");
      return;
    }

    const currentPassword = dom.currentPasswordInput.value.trim();
    const newPassword = dom.newPasswordInput.value.trim();
    const confirmPassword = dom.confirmPasswordInput.value.trim();

    if (!currentPassword || !newPassword || !confirmPassword) {
      setStatus(dom.passwordStatus, "Fill all fields.", "error");
      return;
    }
    if (newPassword.length < 6) {
      setStatus(dom.passwordStatus, "New password must be at least 6 characters.", "error");
      return;
    }
    if (newPassword !== confirmPassword) {
      setStatus(dom.passwordStatus, "Password confirmation does not match.", "error");
      return;
    }

    state.passwordSaving = true;
    dom.changePasswordBtn.disabled = true;
    setStatus(dom.passwordStatus, "Updating password...", "");
    try {
      const result = await api("/account/password", {
        method: "PUT",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_new_password: confirmPassword,
        }),
      });
      dom.currentPasswordInput.value = "";
      dom.newPasswordInput.value = "";
      dom.confirmPasswordInput.value = "";
      setStatus(dom.passwordStatus, result.message || "Password updated successfully.", "success");
    } catch (error) {
      setStatus(dom.passwordStatus, error.message, "error");
    } finally {
      state.passwordSaving = false;
      dom.changePasswordBtn.disabled = false;
    }
  }

  async function logout() {
    await clearAuthToken();
    state.me = null;
    renderProfile();
    renderAccountSettings();
  }

  function bindEvents() {
    dom.emailForm.addEventListener("submit", submitEmailUpdate);
    dom.passwordForm.addEventListener("submit", submitPasswordUpdate);
  }

  function init() {
    renderProfile();
    renderAccountSettings();
    bindEvents();
    loadProfile();
  }

  init();
})();
