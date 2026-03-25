(() => {
  const { renderSidebar, renderAccountMenu, getAccountMenuRefs } = window.appShell;
  const { api, clearAuthToken, escapeHtml, getCurrentUser, initAccountMenu } = window.appCommon;
  const { getAuthModalRefs, initAuthModal } = window.appAuth;

  renderSidebar(document.getElementById("sidebarShell"), {
    active: "decks",
    decksHref: "/deck.html?new=1",
    homeLabel: "Home",
    variant: "panel",
  });
  renderAccountMenu(document.getElementById("accountMenuSlot"), {
    buttonClass: "btn btn-outline-light account-trigger",
    menuClass: "dropdown-menu dropdown-menu-end shadow-sm border-0 rounded-4 p-2",
  });

  const params = new URLSearchParams(window.location.search);
  const deckId = params.get("id");

  const state = {
    me: null,
    deckId,
    deckOwner: null,
    ownerAccess: !deckId,
    savedInLibrary: false,
    shareAccessToken: deckId ? sessionStorage.getItem(`deck-access-${deckId}`) || "" : "",
    draft: {
      name: "",
      description: "",
      tags: [],
      visibility: "public",
      access_password: "",
      cards: [],
      removedCardIds: [],
    },
    isDirty: false,
    dragIndex: null,
    allowBrowserLeave: false,
    imagePickerOpen: false,
    activeImageCardIndex: null,
    imageSearchQuery: "",
    imageSearchPage: 1,
    imageSearchResults: [],
    imageSearchLoading: false,
    imageSearchError: "",
    imageSearchHasSearched: false,
  };

  const sharedApi = (path, options = {}) => {
    const headers = {
      "Content-Type": "application/json",
      ...(state.shareAccessToken ? { "X-Deck-Access-Token": state.shareAccessToken } : {}),
      ...(options.headers || {}),
    };

    return fetch(path, { ...options, headers }).then(async (response) => {
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
    });
  };

  const accountRefs = getAccountMenuRefs();
  const authRefs = getAuthModalRefs();
  const dom = {
    pageTitle: document.getElementById("pageTitle"),
    pageSubtitle: document.getElementById("pageSubtitle"),
    deckOwnerLabel: document.getElementById("deckOwnerLabel"),
    readOnlyBadge: document.getElementById("readOnlyBadge"),
    savedDeckBadge: document.getElementById("savedDeckBadge"),
    deckTitleInput: document.getElementById("deckTitleInput"),
    deckDescriptionInput: document.getElementById("deckDescriptionInput"),
    deckVisibilityInput: document.getElementById("deckVisibilityInput"),
    deckPasswordWrap: document.getElementById("deckPasswordWrap"),
    deckPasswordInput: document.getElementById("deckPasswordInput"),
    visibilityHint: document.getElementById("visibilityHint"),
    shareModeLabel: document.getElementById("shareModeLabel"),
    shareModeHint: document.getElementById("shareModeHint"),
    shareLinkInput: document.getElementById("shareLinkInput"),
    copyShareLinkBtn: document.getElementById("copyShareLinkBtn"),
    deckStatusMessage: document.getElementById("deckStatusMessage"),
    addCardBtn: document.getElementById("addCardBtn"),
    footerAddCardBtn: document.getElementById("footerAddCardBtn"),
    cardsCountChip: document.getElementById("cardsCountChip"),
    cardsList: document.getElementById("cardsList"),
    saveBtn: document.getElementById("saveBtn"),
    bottomAddCardBtn: document.getElementById("bottomAddCardBtn"),
    bottomSaveBtn: document.getElementById("bottomSaveBtn"),
    imagePickerModalElement: document.getElementById("imagePickerModal"),
    imageSearchInput: document.getElementById("imageSearchInput"),
    imageSearchBtn: document.getElementById("imageSearchBtn"),
    imageUploadInput: document.getElementById("imageUploadInput"),
    imagePickerStatus: document.getElementById("imagePickerStatus"),
    imageRefreshBtn: document.getElementById("imageRefreshBtn"),
    imageLoadMoreBtn: document.getElementById("imageLoadMoreBtn"),
    imageResultsGrid: document.getElementById("imageResultsGrid"),
    backLink: document.querySelector(".back-link"),
  };

  const imagePickerModal = new bootstrap.Modal(dom.imagePickerModalElement);

  const authUi = initAuthModal({
    refs: authRefs,
    setStatus,
    onAuthenticated: async () => {
      await loadProfile();
      await loadDeck();
    },
  });

  const accountMenuUi = initAccountMenu({
    refs: accountRefs,
    onLogin: authUi.openLogin,
    onSignup: authUi.openSignup,
    onProfile: () => navigateAway("/"),
    onSettings: () => navigateAway("/settings.html"),
    onLogout: () => {
      if (!confirmLeave()) return;
      clearAuthToken();
      navigateAway("/");
    },
  });

  function setStatus(node, message, type) {
    if (!node) return;
    node.textContent = message || "";
    node.className = "small fw-semibold";
    if (!message) return;
    if (type === "success") node.classList.add("text-success");
    if (type === "error") node.classList.add("text-danger");
    if (!type) node.classList.add("text-secondary");
  }

  function makeCard(card = {}) {
    return {
      localId: card.localId || `card-${crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)}`,
      id: card.id ?? null,
      front: card.front || "",
      back: card.back || "",
      image_url: card.image_url || "",
    };
  }

  function canManageDeck() {
    return !state.deckId || state.ownerAccess;
  }

  function ownerLabel() {
    return state.deckOwner?.owner_name || state.deckOwner?.owner_email || "Unknown creator";
  }

  function markDirty() {
    state.isDirty = true;
  }

  function confirmLeave() {
    if (!state.isDirty) return true;
    return window.confirm("Discard unsaved deck changes?");
  }

  function handleBeforeUnload(event) {
    if (!state.isDirty || state.allowBrowserLeave) return;
    event.preventDefault();
    event.returnValue = "";
  }

  function navigateAway(url) {
    state.allowBrowserLeave = true;
    state.isDirty = false;
    window.removeEventListener("beforeunload", handleBeforeUnload);
    window.location.href = url;
  }

  function renderProfile() {
    accountMenuUi.render(state.me);
  }

  function currentShareLink() {
    if (!state.deckId) return "";
    return `${window.location.origin}/study.html?deck=${state.deckId}`;
  }

  function hydrateDraft(deck) {
    state.deckOwner = deck
      ? {
          owner_id: deck.owner_id,
          owner_name: deck.owner_name,
          owner_email: deck.owner_email,
        }
      : null;
    state.ownerAccess = !deck ? !state.deckId : Boolean(state.me && deck.owner_id === state.me.id);
    state.savedInLibrary = Boolean(deck?.saved_in_library);
    state.draft.name = deck?.name || "";
    state.draft.description = deck?.description || "";
    state.draft.tags = deck?.tags || [];
    state.draft.visibility = deck?.visibility || "public";
    state.draft.access_password = "";
    state.draft.cards = deck?.cards?.length ? deck.cards.map((card) => makeCard(card)) : [makeCard()];
    state.draft.removedCardIds = [];
    state.isDirty = false;
    renderEditor();
  }

  function renderEditor() {
    renderProfile();

    const isEditMode = Boolean(state.deckId);
    const canManage = canManageDeck();

    dom.pageTitle.textContent = !isEditMode ? "Create Deck" : canManage ? "Edit Deck" : "View Deck";
    dom.pageSubtitle.textContent = !isEditMode
      ? "Create deck details and flashcards in one consistent Bootstrap workspace."
      : canManage
        ? "Update deck details and flashcards in one consistent Bootstrap workspace."
        : "This deck is available in read-only mode because you are not the owner.";
    dom.deckOwnerLabel.textContent = state.deckOwner ? `Created by ${ownerLabel()}` : "Created by you";
    dom.readOnlyBadge.classList.toggle("d-none", canManage || !isEditMode);
    dom.savedDeckBadge.classList.toggle("d-none", !state.savedInLibrary || canManage);

    dom.deckTitleInput.value = state.draft.name;
    dom.deckTitleInput.disabled = !canManage;
    dom.deckDescriptionInput.value = state.draft.description;
    dom.deckDescriptionInput.disabled = !canManage;
    dom.deckVisibilityInput.value = state.draft.visibility;
    dom.deckVisibilityInput.disabled = !canManage;
    dom.deckPasswordWrap.classList.toggle("d-none", !canManage || state.draft.visibility !== "private");
    dom.deckPasswordInput.value = state.draft.access_password;
    dom.deckPasswordInput.disabled = !canManage;
    dom.visibilityHint.textContent = state.draft.visibility === "private"
      ? "Anyone with the link must enter the deck password first."
      : "Anyone with the direct link can open this deck.";
    dom.shareModeLabel.textContent = state.draft.visibility === "private" ? "Private link" : "Public link";
    dom.shareModeHint.textContent = state.draft.visibility === "private"
      ? "This link is password-protected. Share the password separately."
      : "This link opens directly for anyone who has it.";
    dom.shareLinkInput.value = currentShareLink() || "Save the deck first to generate a shareable link.";
    dom.copyShareLinkBtn.disabled = !state.deckId;
    dom.cardsCountChip.textContent = `${state.draft.cards.length} cards`;
    dom.saveBtn.innerHTML = isEditMode
      ? '<i class="bi bi-floppy me-2"></i>Save Changes'
      : '<i class="bi bi-plus-circle me-2"></i>Create Deck';
    dom.saveBtn.classList.toggle("d-none", !canManage);
    dom.bottomSaveBtn.classList.toggle("d-none", !canManage);
    dom.addCardBtn.classList.toggle("d-none", !canManage);
    dom.footerAddCardBtn.classList.toggle("d-none", !canManage);
    dom.bottomAddCardBtn.classList.toggle("d-none", !canManage);

    if (!state.draft.cards.length) {
      dom.cardsList.innerHTML = '<div class="alert alert-light border shadow-sm rounded-4 mb-0">No cards yet. Start by adding the first card block.</div>';
      return;
    }

    dom.cardsList.innerHTML = state.draft.cards.map((card, index) => `
      <article class="card border-0 shadow-sm rounded-4 editor-card" draggable="${canManage ? "true" : "false"}" data-card-index="${index}">
        <div class="card-body editor-card-body">
          <div class="compact-card-head">
            <div class="d-flex align-items-center gap-3">
              <span class="card-index-badge">Card ${index + 1}</span>
            </div>
            <div class="card-actions ${canManage ? "" : "d-none"}">
              <button class="btn card-action-btn drag-handle" type="button" aria-label="Reorder card">
                <i class="bi bi-grip-vertical"></i>
              </button>
              <button class="btn card-action-btn" type="button" data-duplicate-card="${index}" title="Duplicate"><i class="bi bi-copy"></i></button>
              <button class="btn card-action-btn action-danger" type="button" data-delete-card="${index}" title="Delete"><i class="bi bi-trash3"></i></button>
            </div>
          </div>
          <div class="compact-card-grid">
            <div>
              <label class="form-label fw-semibold mb-2 card-field-label">Term / Front</label>
              <textarea class="form-control field-textarea bg-dark border-secondary" data-card-front="${index}" rows="3" placeholder="e.g. こんにちは" ${canManage ? "" : "disabled"}>${escapeHtml(card.front)}</textarea>
            </div>
            <div>
              <label class="form-label fw-semibold mb-2 card-field-label">Definition / Back</label>
              <textarea class="form-control field-textarea bg-dark border-secondary" data-card-back="${index}" rows="3" placeholder="e.g. Hello" ${canManage ? "" : "disabled"}>${escapeHtml(card.back)}</textarea>
            </div>
            <div class="compact-thumb-col">
              <div class="thumb-slot">
                <label class="thumb-label">Image</label>
                <div class="thumb-frame ${card.image_url ? "" : "empty"}" ${canManage ? `role="button" tabindex="0" data-open-image-picker="${index}" title="Add image"` : ""}>
                  ${card.image_url ? `<img src="${escapeHtml(card.image_url)}" alt="Card preview" />` : '<div class="thumb-empty-inner"><i class="bi bi-image"></i><span>Add image</span></div>'}
                </div>
                ${card.image_url && canManage ? `<button class="btn thumb-overlay-btn" type="button" data-clear-image="${index}" title="Remove image"><i class="bi bi-x-lg"></i></button>` : ""}
              </div>
            </div>
          </div>
        </div>
      </article>
    `).join("");
  }

  async function loadProfile() {
    state.me = await getCurrentUser(api);
    renderProfile();
  }

  async function loadDeck() {
    if (!state.deckId) {
      hydrateDraft(null);
      return;
    }

    try {
      let deck = null;

      if (state.me) {
        try {
          deck = await api(`/decks/${state.deckId}`);
        } catch (error) {
          // Fall back to shared access below.
        }
      }

      if (!deck) {
        deck = await sharedApi(`/shared/decks/${state.deckId}`);
      }

      hydrateDraft(deck);
    } catch (error) {
      setStatus(dom.deckStatusMessage, error.message, "error");
    }
  }

  function addCard(seed = {}) {
    if (!canManageDeck()) return;
    state.draft.cards.push(makeCard(seed));
    markDirty();
    renderEditor();
  }

  function duplicateCard(index) {
    if (!canManageDeck()) return;
    const card = state.draft.cards[index];
    if (!card) return;

    state.draft.cards.splice(index + 1, 0, makeCard({
      front: card.front,
      back: card.back,
      image_url: card.image_url,
    }));
    markDirty();
    renderEditor();
  }

  function deleteCard(index) {
    if (!canManageDeck()) return;
    const [removed] = state.draft.cards.splice(index, 1);
    if (removed?.id) state.draft.removedCardIds.push(removed.id);
    if (!state.draft.cards.length) state.draft.cards.push(makeCard());
    markDirty();
    renderEditor();
  }

  function updateCardField(index, key, value) {
    if (!canManageDeck()) return;
    const card = state.draft.cards[index];
    if (!card) return;
    card[key] = value;
    markDirty();
  }

  function activeImageCard() {
    if (state.activeImageCardIndex === null) return null;
    return state.draft.cards[state.activeImageCardIndex] || null;
  }

  function renderImagePicker() {
    setStatus(
      dom.imagePickerStatus,
      state.imageSearchError || (state.imageSearchLoading ? "Searching images..." : ""),
      state.imageSearchError ? "error" : "",
    );
    dom.imageSearchInput.value = state.imageSearchQuery;
    dom.imageSearchBtn.disabled = state.imageSearchLoading;
    dom.imageRefreshBtn.disabled = state.imageSearchLoading || !state.imageSearchHasSearched;
    dom.imageLoadMoreBtn.disabled = state.imageSearchLoading;
    dom.imageLoadMoreBtn.classList.toggle("d-none", !state.imageSearchHasSearched || !state.imageSearchResults.length);

    if (state.imageSearchLoading && !state.imageSearchResults.length) {
      dom.imageResultsGrid.innerHTML = '<div class="text-secondary">Loading image suggestions...</div>';
      return;
    }

    if (!state.imageSearchHasSearched) {
      dom.imageResultsGrid.innerHTML = '<div class="text-secondary">Start with a search or use the term field to auto-search.</div>';
      return;
    }

    if (!state.imageSearchResults.length) {
      dom.imageResultsGrid.innerHTML = '<div class="text-secondary">No image results found. Try another query.</div>';
      return;
    }

    dom.imageResultsGrid.innerHTML = state.imageSearchResults.map((result, index) => `
      <button class="image-result-card text-start p-0" type="button" data-select-image="${index}">
        <img src="${escapeHtml(result.thumbnail_url)}" alt="${escapeHtml(result.title)}" loading="lazy" />
        <div class="image-result-meta d-grid gap-1">
          <div class="image-result-title">${escapeHtml(result.title || "Untitled image")}</div>
          <div class="small text-secondary">${escapeHtml(result.author || result.license || result.provider)}</div>
        </div>
      </button>
    `).join("");
  }

  async function searchImages({ append = false, page = 1 } = {}) {
    if (!state.me) {
      state.imageSearchError = "Log in from the avatar menu to search images.";
      renderImagePicker();
      return;
    }

    const query = dom.imageSearchInput.value.trim();
    if (!query) {
      state.imageSearchError = "Enter a search query.";
      renderImagePicker();
      return;
    }

    state.imageSearchLoading = true;
    state.imageSearchError = "";
    state.imageSearchQuery = query;
    renderImagePicker();

    try {
      const response = await api("/images/search", {
        method: "POST",
        body: JSON.stringify({ query, page, page_size: 12 }),
      });
      state.imageSearchPage = page;
      state.imageSearchHasSearched = true;
      state.imageSearchResults = append ? [...state.imageSearchResults, ...response.results] : response.results;
    } catch (error) {
      state.imageSearchError = error.message;
    } finally {
      state.imageSearchLoading = false;
      renderImagePicker();
    }
  }

  function openImagePicker(index) {
    if (!canManageDeck()) return;
    state.activeImageCardIndex = index;
    state.imagePickerOpen = true;
    state.imageSearchError = "";
    state.imageSearchResults = [];
    state.imageSearchHasSearched = false;
    state.imageSearchPage = 1;
    state.imageSearchQuery = state.draft.cards[index]?.front?.trim() || "";
    renderImagePicker();
    imagePickerModal.show();

    if (state.imageSearchQuery) {
      window.setTimeout(() => searchImages({ page: 1 }), 0);
    }
  }

  async function attachSearchedImage(resultIndex) {
    const card = activeImageCard();
    const result = state.imageSearchResults[resultIndex];
    if (!card || !result) return;

    setStatus(dom.imagePickerStatus, "Saving selected image...", "");
    try {
      const stored = await api("/images/import", {
        method: "POST",
        body: JSON.stringify({
          source_url: result.source_url,
          title: result.title || card.front || "card image",
        }),
      });
      updateCardField(state.activeImageCardIndex, "image_url", stored.image_url);
      renderEditor();
      imagePickerModal.hide();
    } catch (error) {
      setStatus(dom.imagePickerStatus, error.message, "error");
    }
  }

  function moveCard(fromIndex, toIndex) {
    if (!canManageDeck()) return;
    if (fromIndex === toIndex || fromIndex === null || toIndex === null) return;
    const [moved] = state.draft.cards.splice(fromIndex, 1);
    state.draft.cards.splice(toIndex, 0, moved);
    markDirty();
    renderEditor();
  }

  async function uploadCardImage(file, index) {
    if (!canManageDeck()) return;
    if (!file) return;
    if (!state.me) {
      throw new Error("Log in from the avatar menu before uploading images.");
    }

    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Failed to read image"));
      reader.readAsDataURL(file);
    });
    const base64Payload = dataUrl.split(",")[1];
    const stored = await api("/images/upload", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name || "upload.jpg",
        content_base64: base64Payload,
      }),
    });
    updateCardField(index, "image_url", stored.image_url);
    renderEditor();
  }

  function validateDraft() {
    const name = state.draft.name.trim();
    if (!name) throw new Error("Deck title is required.");

    if (state.draft.visibility === "private" && !state.deckId && state.draft.access_password.trim().length < 4) {
      throw new Error("Private decks require a password with at least 4 characters.");
    }

    if (state.draft.visibility === "private" && state.draft.access_password.trim() && state.draft.access_password.trim().length < 4) {
      throw new Error("Private decks require a password with at least 4 characters.");
    }

    for (const card of state.draft.cards) {
      const hasFront = card.front.trim();
      const hasBack = card.back.trim();
      if ((hasFront && !hasBack) || (!hasFront && hasBack)) {
        throw new Error("Each card must have both front and back, or stay fully empty.");
      }
    }
  }

  async function saveDeck() {
    if (!canManageDeck()) {
      setStatus(dom.deckStatusMessage, "This deck is read-only because you are not the owner.", "error");
      return;
    }

    if (!state.me) {
      setStatus(dom.deckStatusMessage, "Log in from the avatar menu to save this deck.", "error");
      return;
    }

    try {
      validateDraft();
      setStatus(dom.deckStatusMessage, "", "");
      const filledCards = state.draft.cards.filter((card) => card.front.trim() && card.back.trim());
      let targetDeckId = state.deckId;

      if (!targetDeckId) {
        const created = await api("/decks", {
          method: "POST",
          body: JSON.stringify({
            name: state.draft.name.trim(),
            description: state.draft.description.trim(),
            tags: state.draft.tags,
            visibility: state.draft.visibility,
            access_password: state.draft.access_password.trim(),
            cards: filledCards.map((card) => ({
              front: card.front.trim(),
              back: card.back.trim(),
              image_url: card.image_url || "",
            })),
          }),
        });
        targetDeckId = created.id;
        state.deckId = String(created.id);
        history.replaceState({}, "", `/deck.html?id=${created.id}`);
      } else {
        await api(`/decks/${targetDeckId}`, {
          method: "PUT",
          body: JSON.stringify({
            name: state.draft.name.trim(),
            description: state.draft.description.trim(),
            tags: state.draft.tags,
            visibility: state.draft.visibility,
            access_password: state.draft.access_password.trim(),
          }),
        });

        for (const removedId of state.draft.removedCardIds) {
          await api(`/cards/${removedId}`, { method: "DELETE" });
        }

        const savedCards = [];
        for (const card of filledCards) {
          if (card.id) {
            const updated = await api(`/cards/${card.id}`, {
              method: "PUT",
              body: JSON.stringify({
                front: card.front.trim(),
                back: card.back.trim(),
                image_url: card.image_url || "",
              }),
            });
            savedCards.push(updated);
          } else {
            const createdCard = await api(`/decks/${targetDeckId}/cards`, {
              method: "POST",
              body: JSON.stringify({
                front: card.front.trim(),
                back: card.back.trim(),
                image_url: card.image_url || "",
              }),
            });
            savedCards.push(createdCard);
          }
        }

        if (savedCards.length) {
          await api(`/decks/${targetDeckId}/cards/reorder`, {
            method: "PUT",
            body: JSON.stringify({
              items: savedCards.map((card, index) => ({ id: card.id, position: index })),
            }),
          });
        }
      }

      const freshDeck = await api(`/decks/${targetDeckId}`);
      hydrateDraft(freshDeck);
      setStatus(dom.deckStatusMessage, "Deck saved.", "success");
      navigateAway(`/study.html?deck=${targetDeckId}`);
    } catch (error) {
      setStatus(dom.deckStatusMessage, error.message, "error");
    }
  }

  function leaveEditor() {
    if (!confirmLeave()) return;
    navigateAway("/");
  }

  function bindEvents() {
    dom.addCardBtn.addEventListener("click", () => addCard());
    dom.footerAddCardBtn.addEventListener("click", () => addCard());
    dom.bottomAddCardBtn.addEventListener("click", () => addCard());
    dom.saveBtn.addEventListener("click", saveDeck);
    dom.bottomSaveBtn.addEventListener("click", saveDeck);
    dom.deckTitleInput.addEventListener("input", (event) => {
      state.draft.name = event.target.value;
      markDirty();
    });
    dom.deckDescriptionInput.addEventListener("input", (event) => {
      state.draft.description = event.target.value;
      markDirty();
    });
    dom.deckVisibilityInput.addEventListener("change", (event) => {
      state.draft.visibility = event.target.value;
      if (state.draft.visibility !== "private") state.draft.access_password = "";
      markDirty();
      renderEditor();
    });
    dom.deckPasswordInput.addEventListener("input", (event) => {
      state.draft.access_password = event.target.value;
      markDirty();
    });
    dom.copyShareLinkBtn.addEventListener("click", async () => {
      if (!state.deckId) return;
      await navigator.clipboard.writeText(currentShareLink());
      setStatus(dom.deckStatusMessage, "Deck link copied.", "success");
    });

    dom.cardsList.addEventListener("input", (event) => {
      if (!canManageDeck()) return;
      if (event.target.dataset.cardFront !== undefined) {
        updateCardField(Number(event.target.dataset.cardFront), "front", event.target.value);
      }
      if (event.target.dataset.cardBack !== undefined) {
        updateCardField(Number(event.target.dataset.cardBack), "back", event.target.value);
      }
    });

    dom.cardsList.addEventListener("keydown", (event) => {
      if (!canManageDeck()) return;
      const openImagePickerTile = event.target.closest("[data-open-image-picker]");
      if (!openImagePickerTile) return;
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openImagePicker(Number(openImagePickerTile.dataset.openImagePicker));
    });

    dom.cardsList.addEventListener("click", (event) => {
      if (!canManageDeck()) return;
      const deleteButton = event.target.closest("[data-delete-card]");
      if (deleteButton) {
        deleteCard(Number(deleteButton.dataset.deleteCard));
        return;
      }

      const duplicateButton = event.target.closest("[data-duplicate-card]");
      if (duplicateButton) {
        duplicateCard(Number(duplicateButton.dataset.duplicateCard));
        return;
      }

      const openImagePickerButton = event.target.closest("[data-open-image-picker]");
      if (openImagePickerButton) {
        openImagePicker(Number(openImagePickerButton.dataset.openImagePicker));
        return;
      }

      const clearImageButton = event.target.closest("[data-clear-image]");
      if (clearImageButton) {
        updateCardField(Number(clearImageButton.dataset.clearImage), "image_url", "");
        renderEditor();
      }
    });

    dom.cardsList.addEventListener("dragstart", (event) => {
      if (!canManageDeck()) return;
      const card = event.target.closest("[data-card-index]");
      if (!card) return;
      state.dragIndex = Number(card.dataset.cardIndex);
      card.classList.add("dragging");
    });

    dom.cardsList.addEventListener("dragover", (event) => {
      if (!canManageDeck()) return;
      event.preventDefault();
      const card = event.target.closest("[data-card-index]");
      if (!card) return;
      dom.cardsList.querySelectorAll(".editor-card").forEach((item) => item.classList.remove("drag-over"));
      card.classList.add("drag-over");
    });

    dom.cardsList.addEventListener("drop", (event) => {
      if (!canManageDeck()) return;
      event.preventDefault();
      const card = event.target.closest("[data-card-index]");
      if (!card) return;
      moveCard(state.dragIndex, Number(card.dataset.cardIndex));
      state.dragIndex = null;
    });

    dom.cardsList.addEventListener("dragend", () => {
      if (!canManageDeck()) return;
      state.dragIndex = null;
      dom.cardsList.querySelectorAll(".editor-card").forEach((item) => item.classList.remove("dragging", "drag-over"));
    });

    dom.backLink.addEventListener("click", (event) => {
      event.preventDefault();
      leaveEditor();
    });
    dom.imageSearchBtn.addEventListener("click", () => searchImages({ page: 1 }));
    dom.imageRefreshBtn.addEventListener("click", () => searchImages({ page: 1 }));
    dom.imageLoadMoreBtn.addEventListener("click", () => searchImages({ append: true, page: state.imageSearchPage + 1 }));
    dom.imageSearchInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      searchImages({ page: 1 });
    });
    dom.imageUploadInput.addEventListener("change", async (event) => {
      if (state.activeImageCardIndex === null) return;
      try {
        await uploadCardImage(event.target.files[0], state.activeImageCardIndex);
        imagePickerModal.hide();
      } catch (error) {
        setStatus(dom.imagePickerStatus, error.message, "error");
      }
      event.target.value = "";
    });
    dom.imageResultsGrid.addEventListener("click", (event) => {
      const resultCard = event.target.closest("[data-select-image]");
      if (!resultCard) return;
      attachSearchedImage(Number(resultCard.dataset.selectImage));
    });
    dom.imagePickerModalElement.addEventListener("hidden.bs.modal", () => {
      state.imagePickerOpen = false;
      state.activeImageCardIndex = null;
      state.imageSearchLoading = false;
      dom.imageUploadInput.value = "";
    });
    window.addEventListener("beforeunload", handleBeforeUnload);
  }

  function init() {
    renderEditor();
    bindEvents();
    loadProfile().then(loadDeck);
  }

  init();
})();
