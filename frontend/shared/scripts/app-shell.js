window.appShell = (() => {
  function renderSidebar(container, options = {}) {
    if (!container) return;

    const {
      active = "home",
      variant = "plain",
      homeLabel = "Dashboard",
      homeHref = "/",
      decksLabel = "My Decks",
      decksHref = "/#decksSection",
      quizLabel = "Quiz",
      quizHref = "/quiz",
      settingsLabel = "Settings",
      settingsHref = "/settings.html",
    } = options;

    const navClass = variant === "panel"
      ? "nav nav-pills flex-column gap-2"
      : "nav nav-pills flex-column gap-2 sidebar-nav";
    const brandClass = variant === "panel"
      ? "d-flex align-items-center gap-3 mb-4 fw-semibold fs-5"
      : "d-flex align-items-center gap-3 mb-2 fw-semibold fs-5 px-1";

    const navItems = [
      { key: "home", href: homeHref, icon: "bi-grid-1x2-fill", label: homeLabel },
      { key: "decks", href: decksHref, icon: "bi-collection-fill", label: decksLabel },
      { key: "quiz", href: quizHref, icon: "bi-patch-check-fill", label: quizLabel },
      { key: "settings", href: settingsHref, icon: "bi-sliders", label: settingsLabel },
    ];

    const brandMarkup = `
      <div class="${brandClass}">
        <div class="brand-badge"><i class="bi bi-stack"></i></div>
        <span>TrinDeckly</span>
      </div>
    `;

    const navMarkup = `
      <nav class="${navClass}">
        ${navItems.map((item) => `
          <a class="nav-link ${active === item.key ? "active" : ""}" href="${item.href}">
            <i class="bi ${item.icon} me-2"></i>${item.label}
          </a>
        `).join("")}
      </nav>
    `;

    if (variant === "panel") {
      container.innerHTML = `
        <div class="card surface-card shadow-sm rounded-4 sidebar-panel">
          <div class="card-body p-3 p-xl-4">
            ${brandMarkup}
            ${navMarkup}
          </div>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="sidebar-inner">
        ${brandMarkup}
        ${navMarkup}
      </div>
    `;
  }

  function renderAccountMenu(container, options = {}) {
    if (!container) return;

    const {
      wrapperClass = "dropdown",
      buttonClass = "btn account-trigger",
      menuClass = "dropdown-menu dropdown-menu-end shadow-sm rounded-4 p-2",
      buttonId = "accountBtn",
      menuId = "accountMenu",
      profileHref = "/",
      settingsHref = "/settings.html",
    } = options;

    container.innerHTML = `
      <div class="${wrapperClass}">
        <button class="${buttonClass}" id="${buttonId}" type="button" data-bs-toggle="dropdown" aria-expanded="false">
          <span class="avatar-badge" id="accountAvatar">G</span>
        </button>
        <ul class="${menuClass}" id="${menuId}">
          <li class="account-summary px-3 py-2 d-none" id="accountSummary">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-badge" id="menuAvatar">G</div>
              <div class="min-w-0">
                <strong class="d-block text-truncate" id="profileName">Learner</strong>
                <small class="text-secondary text-truncate d-block" id="profileEmail">learner@example.com</small>
              </div>
            </div>
          </li>
          <li id="guestActions">
            <button class="dropdown-item rounded-3" id="accountLoginBtn" type="button">Log in</button>
          </li>
          <li id="guestSignupWrap">
            <button class="dropdown-item rounded-3" id="accountSignupBtn" type="button">Sign up</button>
          </li>
          <li class="d-none" id="userActions">
            <a class="dropdown-item rounded-3" id="accountProfileBtn" href="${profileHref}">Profile</a>
            <a class="dropdown-item rounded-3" id="accountSettingsBtn" href="${settingsHref}">Settings</a>
            <hr class="dropdown-divider border-secondary my-2">
            <button class="dropdown-item rounded-3 text-danger" id="accountLogoutBtn" type="button">Log out</button>
          </li>
        </ul>
      </div>
    `;
  }

  function getAccountMenuRefs(root = document) {
    return {
      accountAvatar: root.getElementById("accountAvatar"),
      menuAvatar: root.getElementById("menuAvatar"),
      profileName: root.getElementById("profileName"),
      profileEmail: root.getElementById("profileEmail"),
      accountSummary: root.getElementById("accountSummary"),
      guestActions: root.getElementById("guestActions"),
      guestSignupWrap: root.getElementById("guestSignupWrap"),
      userActions: root.getElementById("userActions"),
      accountLoginBtn: root.getElementById("accountLoginBtn"),
      accountSignupBtn: root.getElementById("accountSignupBtn"),
      accountProfileBtn: root.getElementById("accountProfileBtn"),
      accountSettingsBtn: root.getElementById("accountSettingsBtn"),
      accountLogoutBtn: root.getElementById("accountLogoutBtn"),
    };
  }

  return {
    renderSidebar,
    renderAccountMenu,
    getAccountMenuRefs,
  };
})();
