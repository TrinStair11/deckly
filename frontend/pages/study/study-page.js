    const { renderSidebar, renderAccountMenu, getAccountMenuRefs } = window.appShell;
    const { api, clearAuthToken, escapeHtml, getCurrentUser, initAccountMenu } = window.appCommon;
    const { createStudySession } = window.studySession;
    const { createStudyRenderer } = window.studyRender;

    renderSidebar(document.getElementById("sidebarShell"), {
      active: "decks",
      decksHref: "/#decksSection",
      homeLabel: "Home",
      variant: "panel",
    });
    renderAccountMenu(document.getElementById("accountMenuSlot"), {
      buttonClass: "btn btn-outline-light account-trigger header-action-close",
      menuClass: "dropdown-menu dropdown-menu-end rounded-4 p-2",
    });

    const deckRequestHeaders = () => ({
      ...(state.shareAccessToken ? { "X-Deck-Access-Token": state.shareAccessToken } : {}),
    });

    const sharedApi = (path, options = {}) => {
      const headers = {
        "Content-Type": "application/json",
        ...(state.shareAccessToken ? { "X-Deck-Access-Token": state.shareAccessToken } : {}),
        ...(options.headers || {})
      };
      return fetch(path, { ...options, credentials: "same-origin", headers }).then(async (response) => {
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
        const text = await response.text();
        return text ? JSON.parse(text) : null;
      });
    };

    const deckApi = (path, options = {}) => api(path, {
      ...options,
      headers: {
        ...deckRequestHeaders(),
        ...(options.headers || {}),
      },
    });

    const params = new URLSearchParams(window.location.search);
    const deckId = params.get("deck");
    const initialMode = params.get("mode") || "all";
    const initialFocusMode = params.get("focus") === "1";
    const saveDeckIntent = params.get("intent") === "save-deck";

    const MODES = [
      { id: "all", label: "Review All", icon: "bi-stack", copy: "Go through every card in the deck as one full session." },
      { id: "limit", label: "Review Count", icon: "bi-123", copy: "Run a smaller session with 10, 20, 30 or all cards." },
      { id: "interval", label: "Interval Review", icon: "bi-clock-history", copy: "Due cards with spaced repetition rating buttons." },
      { id: "test", label: "Test Mode", icon: "bi-ui-checks-grid", copy: "Multiple choice self-check with score tracking." }
    ];
    const DEFAULT_STUDY_SETTINGS = {
      cardSideOrder: "front",
      shuffleCards: false
    };

    const state = {
      me: null,
      deck: null,
      dueSession: null,
      mode: initialMode,
      sessionCards: [],
      currentIndex: 0,
      revealed: false,
      started: false,
      ownerAccess: false,
      sharedMeta: null,
      shareAccessToken: sessionStorage.getItem(`deck-access-${deckId}`) || "",
      correct: 0,
      incorrect: 0,
      sessionLimit: 10,
      intervalSessionId: "",
      testChoices: [],
      lastAnswer: null,
      reviewAnimating: false,
      reviewExitLabel: "",
      missedCardIds: [],
      actionHistory: [],
      settingsOpen: false,
      cardSideOrder: "front",
      shuffleCards: false,
      focusMode: initialFocusMode
    };

    const {
      accountAvatar,
      menuAvatar,
      profileName,
      profileEmail,
      accountSummary,
      guestActions,
      guestSignupWrap,
      userActions,
      accountLoginBtn,
      accountSignupBtn,
      accountProfileBtn,
      accountSettingsBtn,
      accountLogoutBtn,
    } = getAccountMenuRefs();
    const deckTitle = document.getElementById("deckTitle");
    const deckSubtitle = document.getElementById("deckSubtitle");
    const deckOwnerLabel = document.getElementById("deckOwnerLabel");
    const readOnlyBadge = document.getElementById("readOnlyBadge");
    const savedDeckBadge = document.getElementById("savedDeckBadge");
    const privacyBadge = document.getElementById("privacyBadge");
    const shareAccessHint = document.getElementById("shareAccessHint");
    const cloneDeckBtn = document.getElementById("cloneDeckBtn");
    const editDeckBtn = document.getElementById("editDeckBtn");
    const groupsBtn = document.getElementById("groupsBtn");
    const shareBtn = document.getElementById("shareBtn");
    const openEditorMenuBtn = document.getElementById("openEditorMenuBtn");
    const shuffleNowBtn = document.getElementById("shuffleNowBtn");
    const copyDeckLinkBtn = document.getElementById("copyDeckLinkBtn");
    const modeGrid = document.getElementById("modeGrid");
    const setupPanel = document.getElementById("setupPanel");
    const statsGrid = document.getElementById("statsGrid");
    const cardViewer = document.getElementById("cardViewer");
    const controlBar = document.getElementById("controlBar");
    const focusTopbar = document.getElementById("focusTopbar");
    const focusExitBtn = document.getElementById("focusExitBtn");
    const focusModeChip = document.getElementById("focusModeChip");
    const focusDeckTitleLabel = document.getElementById("focusDeckTitleLabel");
    const focusProgressPill = document.getElementById("focusProgressPill");

    const sessionActions = {
      renderAll: null,
      renderControls: null,
      startMode: null,
      modeLabel: null,
    };

    const studySession = createStudySession({
      state,
      dom: {
        focusTopbar,
        focusProgressPill,
        focusDeckTitleLabel,
        focusModeChip,
        cardViewer,
      },
      helpers: {
        api: deckApi,
        sharedApi,
      },
      config: {
        DEFAULT_STUDY_SETTINGS,
        deckId,
      },
      actions: sessionActions,
    });

    const {
      saveStudySettings,
      loadStudySettings,
      shuffle,
      currentCard,
      captureSessionSnapshot,
      pushSessionUndo,
      canUndoSessionAction,
      undoLastSessionAction,
      isSessionActive,
      isSessionCompleted,
      syncStudyFocusLayout,
      toggleFocusMode,
      primaryCardSide,
      secondaryCardSide,
      currentSideLabel,
      buildIntervalRatingPreviews,
      loadIntervalSession,
      startCurrentSessionWithSettings,
      syncFlipPresentation,
    } = studySession;

    const accountMenuUi = initAccountMenu({
      refs: {
        accountAvatar,
        menuAvatar,
        profileName,
        profileEmail,
        accountSummary,
        guestActions,
        guestSignupWrap,
        userActions,
        accountLoginBtn,
        accountSignupBtn,
        accountProfileBtn,
        accountSettingsBtn,
        accountLogoutBtn,
      },
      onLogin: () => { window.location.href = "/"; },
      onSignup: () => { window.location.href = "/"; },
      onProfile: () => { window.location.href = "/"; },
      onSettings: () => { window.location.href = "/settings.html"; },
      onLogout: logout,
    });

    const rendererActions = {
      loadDeck,
      toggleFocusMode,
      undoLastSessionAction,
      saveStudySettings,
      startCurrentSessionWithSettings,
      renderAll: null,
    };

    const renderer = createStudyRenderer({
      state,
      dom: {
        modeGrid,
        setupPanel,
        deckTitle,
        deckSubtitle,
        deckOwnerLabel,
        readOnlyBadge,
        savedDeckBadge,
        privacyBadge,
        shareAccessHint,
        cloneDeckBtn,
        editDeckBtn,
        groupsBtn,
        openEditorMenuBtn,
        statsGrid,
        cardViewer,
        controlBar,
      },
      helpers: {
        MODES,
        api,
        escapeHtml,
        sharedApi,
        isSessionCompleted,
        isSessionActive,
        currentCard,
        primaryCardSide,
        secondaryCardSide,
        currentSideLabel,
        buildIntervalRatingPreviews,
        canUndoSessionAction,
        shuffle,
        syncFlipPresentation,
        captureSessionSnapshot,
        pushSessionUndo,
      },
      actions: rendererActions,
      accountMenuUi,
      config: { deckId },
    });

    const {
      renderProfile,
      renderModes,
      renderSetup,
      modeLabel,
      setViewerSessionMode,
      currentDeckLink,
      renderPrivacyState,
      renderHeader,
      renderStats,
      buildTestChoices,
      startMode,
      flipCurrentCard,
      completeSelfCheck,
      submitIntervalRating,
      nextTestCard,
      renderViewer,
      renderControls,
      renderAccessGate,
    } = renderer;

    function renderAll() {
      renderHeader();
      renderModes();
      renderSetup();
      renderStats();
      renderViewer();
      renderControls();
      syncStudyFocusLayout();
    }

    rendererActions.renderAll = renderAll;
    sessionActions.renderAll = renderAll;
    sessionActions.renderControls = renderControls;
    sessionActions.startMode = startMode;
    sessionActions.modeLabel = modeLabel;

    async function loadProfile() {
      state.me = await getCurrentUser(api);
      loadStudySettings();
      renderProfile();
    }

    function clearSaveDeckIntent() {
      if (!saveDeckIntent) return;
      const url = new URL(window.location.href);
      url.searchParams.delete("intent");
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }

    function buildSaveAfterLoginUrl() {
      const nextUrl = new URL("/study.html", window.location.origin);
      if (deckId) nextUrl.searchParams.set("deck", deckId);
      nextUrl.searchParams.set("intent", "save-deck");

      const loginUrl = new URL("/", window.location.origin);
      loginUrl.searchParams.set("auth", "login");
      loginUrl.searchParams.set("next", `${nextUrl.pathname}${nextUrl.search}`);
      return loginUrl.toString();
    }

    function openWordList(event) {
      if (event) event.preventDefault();
      if (!deckId) return;
      window.location.href = `/deck.html?id=${deckId}&view=interval`;
    }

    async function saveDeckToLibrary() {
      const saved = await sharedApi(`/shared/decks/${deckId}/save`, { method: "POST" });
      state.deck = { ...state.deck, ...saved };
      renderAll();
      return saved;
    }

    async function maybeCompleteSaveIntent() {
      if (!saveDeckIntent || !state.me || !state.deck) return;
      if (state.ownerAccess || state.deck.saved_in_library) {
        clearSaveDeckIntent();
        return;
      }

      cloneDeckBtn.disabled = true;
      try {
        await saveDeckToLibrary();
      } catch (error) {
        window.alert(error.message);
      } finally {
        cloneDeckBtn.disabled = false;
        clearSaveDeckIntent();
      }
    }

    async function loadDeck() {
      if (!deckId) {
        setViewerSessionMode(false);
        cardViewer.innerHTML = '<div class="card-body text-center text-secondary">Study deck is not specified.</div>';
        return;
      }
      try {
        if (state.me) {
        try {
            const deck = await deckApi(`/decks/${deckId}`);
            state.ownerAccess = Boolean(deck.is_owner);
            state.sharedMeta = null;
            state.deck = deck;
            await loadIntervalSession();
            startMode(MODES.some((mode) => mode.id === initialMode) ? initialMode : 'all');
            await maybeCompleteSaveIntent();
            return;
          } catch (error) {
            state.ownerAccess = false;
          }
        }

        const meta = await sharedApi(`/shared/decks/${deckId}/meta`, { headers: {} });
        state.sharedMeta = meta;
        deckTitle.textContent = meta.name;
        deckSubtitle.textContent = meta.visibility === "private"
          ? "This shared deck is password-protected."
          : "This shared deck is available by direct link.";
        renderPrivacyState();
        if (meta.visibility === "private" && !state.shareAccessToken) {
          state.deck = null;
          state.dueSession = null;
          renderAccessGate();
          return;
        }
        const [deck, dueSession] = await Promise.all([sharedApi(`/shared/decks/${deckId}`), sharedApi(`/shared/decks/${deckId}/study`)]);
        state.deck = deck;
        state.dueSession = dueSession;
        startMode(MODES.some((mode) => mode.id === initialMode) ? initialMode : 'all');
        await maybeCompleteSaveIntent();
      } catch (error) {
        if (error.message === "Password is required for this deck") {
          state.shareAccessToken = "";
          sessionStorage.removeItem(`deck-access-${deckId}`);
          renderAccessGate();
          return;
        }
        setViewerSessionMode(false);
        cardViewer.innerHTML = `<div class="card-body text-center text-danger">${escapeHtml(error.message)}</div>`;
      }
    }

    async function logout() {
      await clearAuthToken();
      window.location.href = '/';
    }

    modeGrid.addEventListener('click', (event) => {
      const button = event.target.closest('[data-mode]');
      if (!button) return;
      startMode(button.dataset.mode);
    });

    setupPanel.addEventListener('click', async (event) => {
      const limitButton = event.target.closest('[data-limit]');
      if (limitButton) {
        state.sessionLimit = limitButton.dataset.limit === 'all' ? 'all' : Number(limitButton.dataset.limit);
        renderSetup();
        return;
      }
      if (event.target.id === 'randomToggleBtn') {
        state.shuffleCards = !state.shuffleCards;
        saveStudySettings();
        renderSetup();
        return;
      }
      if (event.target.id === 'startLimitBtn') {
        const source = state.shuffleCards ? shuffle(state.deck.cards) : [...state.deck.cards];
        state.sessionCards = source.slice(0, state.sessionLimit === 'all' ? source.length : Number(state.sessionLimit));
        state.started = true;
        state.currentIndex = 0;
        state.correct = 0;
        state.incorrect = 0;
        state.revealed = false;
        renderAll();
        return;
      }
      if (event.target.id === 'startIntervalBtn') {
        await loadIntervalSession();
        startMode('interval');
      }
    });

    editDeckBtn.addEventListener('click', openWordList);
    openEditorMenuBtn.addEventListener('click', openWordList);
    cloneDeckBtn.addEventListener('click', async () => {
      if (!state.deck || state.ownerAccess) return;
      if (!state.me) {
        window.location.href = buildSaveAfterLoginUrl();
        return;
      }
      cloneDeckBtn.disabled = true;
      try {
        await saveDeckToLibrary();
      } catch (error) {
        window.alert(error.message);
      } finally {
        cloneDeckBtn.disabled = false;
      }
    });
    shuffleNowBtn.addEventListener('click', () => {
      if (state.sessionCards.length) {
        state.sessionCards = shuffle(state.sessionCards);
        state.currentIndex = 0;
        state.revealed = false;
        state.lastAnswer = null;
        state.actionHistory = [];
        if (state.mode === 'test' && state.sessionCards[0]) state.testChoices = buildTestChoices(state.sessionCards[0]);
        renderAll();
      }
    });
    copyDeckLinkBtn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(currentDeckLink());
    });
    groupsBtn.addEventListener('click', () => window.alert('Groups are not implemented yet.'));
    shareBtn.addEventListener('click', async () => {
      if (navigator.share) {
        try {
          await navigator.share({
            title: state.deck?.name || state.sharedMeta?.name || 'Deck',
            text: state.deck?.visibility === 'private' || state.sharedMeta?.visibility === 'private'
              ? 'Private TrinDeckly deck link. A password is required.'
              : 'Public TrinDeckly deck link.',
            url: currentDeckLink()
          });
          return;
        } catch (error) {
          return;
        }
      }
      await navigator.clipboard.writeText(currentDeckLink());
      window.alert('Deck link copied.');
    });
    if (focusExitBtn) focusExitBtn.addEventListener('click', () => toggleFocusMode(false));
    document.addEventListener('fullscreenchange', () => {
      if (document.fullscreenElement || !state.focusMode) return;
      state.focusMode = false;
      syncStudyFocusLayout();
      renderControls();
    });
    document.addEventListener('click', (event) => {
      if (!state.settingsOpen) return;
      if (event.target.closest('[data-settings-shell]')) return;
      state.settingsOpen = false;
      renderControls();
    });
    document.addEventListener('keydown', (event) => {
      if (state.settingsOpen && event.key === 'Escape') {
        state.settingsOpen = false;
        renderControls();
        return;
      }
      if (state.focusMode && event.key === 'Escape') {
        event.preventDefault();
        toggleFocusMode(false);
        return;
      }
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (!state.mode || !state.sessionCards.length) return;
      if (!state.started && (state.mode === 'limit' || state.mode === 'interval')) return;
      if (state.reviewAnimating) return;

      const isUndoShortcut = event.key === 'z' || event.key === 'Z';
      if (isUndoShortcut) {
        if (!canUndoSessionAction()) return;
        event.preventDefault();
        undoLastSessionAction();
        return;
      }

      if (state.currentIndex >= state.sessionCards.length) return;

      if (event.key === 'f' || event.key === 'F') {
        event.preventDefault();
        toggleFocusMode();
        return;
      }

      const isSpace = event.code === 'Space' || event.key === ' ' || event.key === 'Spacebar';
      if (isSpace) {
        event.preventDefault();
        flipCurrentCard();
        return;
      }

      if (state.mode === 'interval' && state.revealed) {
        const ratingHotkeys = {
          '1': 'again',
          '2': 'hard',
          '3': 'good',
          '4': 'easy'
        };
        const rating = ratingHotkeys[event.key];
        if (rating) {
          event.preventDefault();
          submitIntervalRating(rating);
          return;
        }
      }

      if ((state.mode === 'all' || state.mode === 'limit') && event.key === 'ArrowLeft') {
        event.preventDefault();
        completeSelfCheck(false);
        return;
      }

      if ((state.mode === 'all' || state.mode === 'limit') && event.key === 'ArrowRight') {
        event.preventDefault();
        completeSelfCheck(true);
      }
    });

    loadProfile().then(loadDeck);
