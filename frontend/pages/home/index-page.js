(() => {
  const { renderSidebar, renderAccountMenu, getAccountMenuRefs } = window.appShell;
  const { api, clearAuthToken, escapeHtml, getCurrentUser, initAccountMenu } = window.appCommon;
  const { getAuthModalRefs, initAuthModal } = window.appAuth;
  const pageParams = new URLSearchParams(window.location.search);
  const requestedAuthMode = pageParams.get("auth");

  renderSidebar(document.getElementById("sidebarShell"), {
    active: "home",
    decksHref: "#decksSection",
    homeLabel: "Dashboard",
  });
  renderAccountMenu(document.getElementById("accountMenuSlot"), {
    wrapperClass: "dropdown hero-account",
    menuClass: "dropdown-menu dropdown-menu-end shadow-sm rounded-4 p-2",
  });

  const state = {
    me: null,
    decks: [],
    sortMode: "updated",
    showOnlyActive: false,
    singleColumn: false,
    openDeckMenuId: null,
  };

  const accountRefs = getAccountMenuRefs();
  const authRefs = getAuthModalRefs();
  const dom = {
    headerSubtitle: document.getElementById("headerSubtitle"),
    createDeckBtn: document.getElementById("createDeckBtn"),
    statCards: document.getElementById("statCards"),
    statLearned: document.getElementById("statLearned"),
    learnedBadge: document.getElementById("learnedBadge"),
    statDue: document.getElementById("statDue"),
    statStreak: document.getElementById("statStreak"),
    decksGrid: document.getElementById("decksGrid"),
    searchInput: document.getElementById("searchInput"),
    sortBtn: document.getElementById("sortBtn"),
    layoutBtn: document.getElementById("layoutBtn"),
    filterBtn: document.getElementById("filterBtn"),
  };

  function getPostAuthRedirectPath() {
    const next = pageParams.get("next") || "";
    if (!next.startsWith("/") || next.startsWith("//")) return "";
    return next;
  }

  const authUi = initAuthModal({
    refs: authRefs,
    setStatus,
    onAuthenticated: async () => {
      await loadProfile();
      const nextPath = getPostAuthRedirectPath();
      if (nextPath) {
        window.location.href = nextPath;
      }
    },
  });

  const accountMenuUi = initAccountMenu({
    refs: accountRefs,
    onLogin: authUi.openLogin,
    onSignup: authUi.openSignup,
    onProfile: () => {
      window.location.href = "/";
    },
    onSettings: () => {
      window.location.href = "/settings.html";
    },
    onLogout: logout,
  });

  function setStatus(node, message, type) {
    if (!node) return;
    node.textContent = message || "";
    node.className = "status small fw-semibold";
    if (message && type) node.classList.add(type);
  }

  function summarizeDeckProgress(decks) {
    return decks.reduce((summary, deck) => {
      const progress = deck.progress || null;
      summary.totalCards += Number(progress?.total_cards ?? deck.card_count ?? 0);
      summary.dueCards += Number(progress?.due_review_count ?? 0);
      summary.learnedCards += Number(progress?.known_count ?? 0);
      return summary;
    }, { totalCards: 0, dueCards: 0, learnedCards: 0 });
  }

  function getDeckTimestamp(deck) {
    return deck.updated_at || deck.created_at;
  }

  function formatUpdated(dateString) {
    if (!dateString) return "Updated recently";

    const diffMinutes = Math.max(1, Math.round((Date.now() - new Date(dateString).getTime()) / 60000));
    if (diffMinutes < 60) return `Updated ${diffMinutes} minutes ago`;

    const hours = Math.round(diffMinutes / 60);
    if (hours < 24) return `Updated ${hours} hours ago`;

    const days = Math.round(hours / 24);
    return `Updated ${days} days ago`;
  }

  function syncSortButton() {
    dom.sortBtn.textContent = state.sortMode === "updated" ? "Sort by Updated" : "Sort by Name";
  }

  function syncFilterButton() {
    dom.filterBtn.textContent = state.showOnlyActive ? "Filter: Active" : "Filter";
  }

  function syncLayoutButton() {
    dom.layoutBtn.innerHTML = state.singleColumn
      ? '<i class="bi bi-grid-1x2"></i>'
      : '<i class="bi bi-grid-3x2-gap"></i>';
  }

  function renderProfile() {
    accountMenuUi.render(state.me);
  }

  function renderStats() {
    const { totalCards, dueCards, learnedCards } = summarizeDeckProgress(state.decks);
    const learnedRatio = totalCards ? Math.round((learnedCards / totalCards) * 100) : 0;

    dom.statCards.textContent = String(totalCards);
    dom.statLearned.textContent = String(learnedCards);
    dom.learnedBadge.textContent = `+${learnedRatio}%`;
    dom.statDue.textContent = String(dueCards);
    dom.statStreak.textContent = `${state.decks.length ? Math.min(5, state.decks.length + 1) : 0} days`;
    dom.headerSubtitle.textContent = `You have ${dueCards} cards to review today.`;
  }

  function getDeckTags(deck) {
    const firstWord = deck.name.split(" ")[0] || "Deck";
    const secondWord = deck.name.split(" ")[1] || "Study";
    return [firstWord, secondWord];
  }

  function renderDecks() {
    const query = dom.searchInput.value.trim().toLowerCase();
    let decks = [...state.decks];

    if (query) {
      decks = decks.filter((deck) => {
        const description = (deck.description || "").toLowerCase();
        return deck.name.toLowerCase().includes(query) || description.includes(query);
      });
    }

    if (state.showOnlyActive) {
      decks = decks.filter((deck) => deck.card_count > 0);
    }

    decks.sort((left, right) => {
      if (state.sortMode === "name") {
        return left.name.localeCompare(right.name);
      }
      return new Date(getDeckTimestamp(right)) - new Date(getDeckTimestamp(left));
    });

    if (!state.me) {
      dom.decksGrid.innerHTML = `
        <div class="col-12">
          <div class="empty-state">
            <div class="empty-state-icon"><i class="bi bi-person-lock"></i></div>
            <h3>Sign in to access your decks</h3>
            <p>Use the avatar in the top-right corner to log in or create an account before managing decks.</p>
            <button class="btn btn-outline-light rounded-pill px-4" type="button" data-open-auth>Log in</button>
          </div>
        </div>
      `;
      return;
    }

    if (!decks.length) {
      const emptyTitle = query || state.showOnlyActive ? "No decks match current filters" : "No decks yet";
      const emptyHint = query || state.showOnlyActive
        ? "Clear the search or filter to see more decks."
        : "Create your first deck to start building your study workspace.";

      dom.decksGrid.innerHTML = `
        <div class="col-12">
          <div class="empty-state">
            <div class="empty-state-icon"><i class="bi bi-collection"></i></div>
            <h3>${emptyTitle}</h3>
            <p>${emptyHint}</p>
            <button class="btn btn-light text-dark rounded-pill px-4" type="button" data-empty-create>Create New Deck</button>
          </div>
        </div>
      `;
      return;
    }

    const colClass = state.singleColumn ? "col-12" : "col-12 col-xl-6";
    dom.decksGrid.innerHTML = decks.map((deck) => {
      const tags = deck.tags && deck.tags.length ? deck.tags : getDeckTags(deck);
      const visibilityClass = deck.visibility === "private" ? "status-private" : "status-public";
      const visibilityLabel = deck.visibility === "private" ? "Private" : "Public";
      const ownerName = deck.owner_name || "Unknown creator";

      return `
        <div class="${colClass}">
          <article class="card deck-card h-100 rounded-4 shadow-sm" data-open-deck="${deck.id}" style="cursor:pointer;">
            <div class="card-body deck-card-body">
              <div class="deck-head">
                <div class="deck-heading">
                  <div class="deck-status-row">
                    <span class="status-badge ${visibilityClass}">${visibilityLabel}</span>
                    ${deck.saved_in_library ? '<span class="status-badge status-neutral">Saved</span>' : ""}
                  </div>
                  <h3 class="deck-title">${escapeHtml(deck.name)}</h3>
                  <p class="deck-description">${escapeHtml(deck.description || "A focused deck for daily recall practice.")}</p>
                  <p class="deck-owner mb-0">Created by ${escapeHtml(ownerName)}</p>
                </div>
                <div class="dropdown ${deck.is_owner ? "" : "d-none"}">
                  <button class="btn btn-sm btn-outline-light deck-menu-trigger" type="button" data-deck-menu="${deck.id}"><i class="bi bi-three-dots"></i></button>
                  <div class="dropdown-menu dropdown-menu-end p-2 ${state.openDeckMenuId === deck.id ? "show" : ""}">
                    <button class="dropdown-item rounded-3" type="button" data-edit-deck="${deck.id}">Edit Deck</button>
                    <button class="dropdown-item rounded-3 text-danger" type="button" data-delete-deck="${deck.id}">Delete Deck</button>
                  </div>
                </div>
              </div>
              <div class="deck-tags">${tags.slice(0, 4).map((tag) => `<span class="deck-tag">${escapeHtml(tag)}</span>`).join("")}</div>
              <div class="deck-footer">
                <div class="small deck-meta d-grid gap-1">
                  <span><i class="bi bi-postcard me-1"></i>${deck.card_count} cards</span>
                  <span><i class="bi bi-clock-history me-1"></i>${formatUpdated(getDeckTimestamp(deck))}</span>
                  <span><i class="bi bi-link-45deg me-1"></i>${deck.visibility === "private" ? "Password-protected link" : "Open link access"}</span>
                </div>
                <a class="btn study-action study-btn" href="/study.html?deck=${deck.id}">
                  <i class="bi bi-play-fill"></i>Study
                </a>
              </div>
            </div>
          </article>
        </div>
      `;
    }).join("");
  }

  async function refreshData() {
    if (!state.me) {
      state.decks = [];
    } else {
      state.decks = await api("/decks");
    }

    renderProfile();
    renderStats();
    renderDecks();
  }

  async function loadProfile() {
    state.me = await getCurrentUser(api);

    try {
      await refreshData();
    } catch (error) {
      window.alert(error.message);
    }
  }

  function goToCreateDeck() {
    window.location.href = "/deck.html?new=1";
  }

  async function handleDeckDelete(deckId) {
    const deck = state.decks.find((item) => item.id === deckId);
    if (!deck) return;

    const confirmed = window.confirm(`Delete "${deck.name}"? This will remove all cards in the deck.`);
    if (!confirmed) return;

    try {
      await api(`/decks/${deckId}`, { method: "DELETE" });
      state.openDeckMenuId = null;
      await refreshData();
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function logout() {
    await clearAuthToken();
    state.me = null;
    state.decks = [];
    state.openDeckMenuId = null;
    renderProfile();
    renderStats();
    renderDecks();
  }

  async function handleInitialRouteState() {
    await loadProfile();
    if (state.me) {
      const nextPath = getPostAuthRedirectPath();
      if (requestedAuthMode && nextPath) {
        window.location.href = nextPath;
      }
      return;
    }

    if (requestedAuthMode === "signup") {
      authUi.openSignup();
    } else if (requestedAuthMode === "login") {
      authUi.openLogin();
    }
  }

  function bindEvents() {
    dom.createDeckBtn.addEventListener("click", goToCreateDeck);
    dom.searchInput.addEventListener("input", renderDecks);
    dom.sortBtn.addEventListener("click", () => {
      state.sortMode = state.sortMode === "updated" ? "name" : "updated";
      syncSortButton();
      renderDecks();
    });
    dom.filterBtn.addEventListener("click", () => {
      state.showOnlyActive = !state.showOnlyActive;
      syncFilterButton();
      renderDecks();
    });
    dom.layoutBtn.addEventListener("click", () => {
      state.singleColumn = !state.singleColumn;
      syncLayoutButton();
      renderDecks();
    });
    dom.decksGrid.addEventListener("click", (event) => {
      const openAuthButton = event.target.closest("[data-open-auth]");
      if (openAuthButton) {
        authUi.openLogin();
        return;
      }

      const createFromEmptyState = event.target.closest("[data-empty-create]");
      if (createFromEmptyState) {
        goToCreateDeck();
        return;
      }

      const menuButton = event.target.closest("[data-deck-menu]");
      if (menuButton) {
        event.stopPropagation();
        state.openDeckMenuId = state.openDeckMenuId === Number(menuButton.dataset.deckMenu)
          ? null
          : Number(menuButton.dataset.deckMenu);
        renderDecks();
        return;
      }

      const openDeckCard = event.target.closest("[data-open-deck]");
      if (openDeckCard && !event.target.closest(".dropdown") && !event.target.closest(".study-btn")) {
        window.location.href = `/study.html?deck=${openDeckCard.dataset.openDeck}`;
        return;
      }

      const editButton = event.target.closest("[data-edit-deck]");
      if (editButton) {
        state.openDeckMenuId = null;
        renderDecks();
        window.location.href = `/deck.html?id=${editButton.dataset.editDeck}`;
        return;
      }

      const deleteButton = event.target.closest("[data-delete-deck]");
      if (deleteButton) {
        handleDeckDelete(Number(deleteButton.dataset.deleteDeck));
      }
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".dropdown") && state.openDeckMenuId !== null) {
        state.openDeckMenuId = null;
        renderDecks();
      }
    });
  }

  function init() {
    syncSortButton();
    syncFilterButton();
    syncLayoutButton();
    renderProfile();
    renderStats();
    renderDecks();
    bindEvents();
    handleInitialRouteState();
  }

  init();
})();
