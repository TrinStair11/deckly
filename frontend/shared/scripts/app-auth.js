window.appAuth = (() => {
  const { api } = window.appCommon;

  function getAuthModalRefs({ root = document, emailId = "email", passwordId = "password" } = {}) {
    return {
      modalElement: root.getElementById("authModal"),
      closeButton: root.getElementById("closeModalBtn"),
      loginTab: root.getElementById("loginTab"),
      registerTab: root.getElementById("registerTab"),
      form: root.getElementById("authForm"),
      emailInput: root.getElementById(emailId),
      passwordInput: root.getElementById(passwordId),
      submitButton: root.getElementById("authSubmitBtn"),
      statusNode: root.getElementById("authStatus"),
    };
  }

  function setNodeStatus(setStatus, node, message, type) {
    if (typeof setStatus === "function") {
      setStatus(node, message, type);
      return;
    }
    if (!node) return;
    node.textContent = message || "";
  }

  function initAuthModal({
    refs,
    setStatus,
    onAuthenticated,
    apiClient = api,
    initialMode = "login",
  } = {}) {
    let mode = initialMode;
    const modal = refs.modal || new bootstrap.Modal(refs.modalElement);

    function syncMode() {
      refs.loginTab?.classList.toggle("active", mode === "login");
      refs.registerTab?.classList.toggle("active", mode === "register");
      if (refs.submitButton) {
        refs.submitButton.textContent = mode === "login" ? "Login" : "Register";
      }
      setNodeStatus(setStatus, refs.statusNode, "", "");
    }

    function open(nextMode = mode) {
      mode = nextMode;
      syncMode();
      modal.show();
    }

    function openLogin() {
      open("login");
    }

    function openSignup() {
      open("register");
    }

    function close() {
      modal.hide();
    }

    async function authenticate() {
      const email = refs.emailInput?.value.trim();
      const password = refs.passwordInput?.value.trim();
      if (!email || !password) {
        setNodeStatus(setStatus, refs.statusNode, "Fill email and password.", "error");
        return null;
      }

      if (refs.submitButton) refs.submitButton.disabled = true;
      try {
        if (mode === "register") {
          await apiClient("/register", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
        }

        const token = await apiClient("/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        if (typeof onAuthenticated === "function") {
          await onAuthenticated({ email, mode, token });
        }
        setNodeStatus(setStatus, refs.statusNode, "Logged in successfully.", "success");
        close();
        return token;
      } catch (error) {
        setNodeStatus(setStatus, refs.statusNode, error.message, "error");
        return null;
      } finally {
        if (refs.submitButton) refs.submitButton.disabled = false;
      }
    }

    refs.closeButton?.addEventListener("click", close);
    refs.loginTab?.addEventListener("click", () => {
      mode = "login";
      syncMode();
    });
    refs.registerTab?.addEventListener("click", () => {
      mode = "register";
      syncMode();
    });
    refs.form?.addEventListener("submit", (event) => {
      event.preventDefault();
      authenticate();
    });

    syncMode();

    return {
      authenticate,
      close,
      open,
      openLogin,
      openSignup,
      syncMode,
    };
  }

  return { getAuthModalRefs, initAuthModal };
})();
