# TrinDeckly

TrinDeckly is a full-stack learning app built with FastAPI, SQLite, and a static Bootstrap frontend. It combines two related workflows in one codebase:

- flashcard decks with spaced repetition, sharing, and focused study modes
- a standalone quiz module with authored questions, scored attempts, results, and review pages

The FastAPI app serves the JSON API, uploaded media, and the shipped frontend from a single process.

## What Is In The App

- JWT authentication with registration, login, profile lookup, email change, and password change
- deck authoring with create, update, delete, reorder, and image-backed cards
- study modes for decks:
  - review all cards
  - limited review sessions
  - interval review using spaced repetition state
  - test mode for self-check
- deck sharing:
  - public link sharing
  - private password-protected sharing
  - save a shared deck into a personal library
- image workflows:
  - search images through Openverse
  - import external image URLs
  - upload local images as base64 payloads
- standalone quiz workflow:
  - quiz library
  - quiz detail and editor screens
  - quiz attempts with answer persistence
  - scored results and per-question review
- static frontend pages for dashboard, deck editor, study hub, settings, and quiz flows

## Stack

- Backend: FastAPI, SQLAlchemy 2.x, Pydantic 1.x
- Database: SQLite
- Auth: `python-jose`, `bcrypt`
- HTTP client: `httpx`
- Frontend: static HTML, vanilla JavaScript, Bootstrap 5, Bootstrap Icons
- Testing: `pytest`, `pytest-cov`

## Repository Layout

```text
backend/
  auth.py                Authentication, JWT helpers, password hashing
  db.py                  SQLite engine and lightweight schema bootstrap
  main.py                Core API routes for auth, decks, study, sharing, images
  quiz_router.py         Quiz API routes and pretty frontend quiz routes
  quizzes.py             Quiz domain helpers and serialization
  models.py              SQLAlchemy models
  schemas.py             Pydantic request/response models
  spaced_repetition.py   Deck review scheduling and progress logic
  time_utils.py          UTC-safe datetime helpers

frontend/
  index.html             Dashboard / deck library
  deck.html              Deck editor and sharing UI
  study.html             Study hub and active review UI
  settings.html          Account settings UI
  quiz.html              Quiz library
  quiz-detail.html       Quiz detail page
  quiz-editor.html       Quiz create/edit page
  quiz-session.html      Quiz attempt flow
  quiz-results.html      Quiz result summary
  quiz-review.html       Quiz answer review
  app-common.js          Shared API/auth helpers for the main app pages
  app-auth.js            Auth modal logic
  app-shell.js           Shared sidebar/account shell rendering
  study-*.js             Split study session, render, viewer, and controls logic
  quiz-common.js         Shared quiz frontend helpers
  quiz-common.css        Shared quiz styling

tests/
  test_auth.py
  test_db.py
  test_main.py
  test_models.py
  test_quiz.py
  test_schemas.py
```

## Quick Start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
uvicorn backend.main:app --reload
```

Open these URLs after startup:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`
- Quiz library: `http://127.0.0.1:8000/quiz`

On first start the app will create:

- `deckly.db` in the repository root
- `media/` for uploaded or imported images

## Configuration

The project runs locally without extra configuration, but these environment variables are supported:

```bash
export SECRET_KEY="replace-this-in-real-environments"
export OPENVERSE_API_URL="https://api.openverse.org/v1/images/"
```

Notes:

- `SECRET_KEY` defaults to a development value in `backend/auth.py`.
- Auth tokens and private deck access tokens are signed with `SECRET_KEY`.
- `OPENVERSE_API_URL` defaults to the public Openverse image API.
- Media files are stored in `media/` and served from `/media/...`.

## Running Tests

Run tests from the repository root with:

```bash
PYTHONPATH=. pytest
```

Test configuration lives in `pytest.ini` and currently enforces backend coverage of at least `85%`.

## API Overview

### Authentication

- `POST /register`
- `POST /login`
- `GET /me`
- `PUT /account/email`
- `PUT /account/password`

### Decks And Cards

- `POST /decks`
- `GET /decks`
- `GET /decks/{deck_id}`
- `PUT /decks/{deck_id}`
- `DELETE /decks/{deck_id}`
- `POST /decks/{deck_id}/cards`
- `PUT /cards/{card_id}`
- `DELETE /cards/{card_id}`
- `PUT /decks/{deck_id}/cards/reorder`
- `GET /cards`

### Study And Progress

- `GET /decks/{deck_id}/study/session`
- `GET /decks/{deck_id}/study`
- `GET /decks/{deck_id}/progress`
- `POST /reviews/submit`
- `POST /cards/{card_id}/review`

### Deck Sharing

- `GET /shared/decks/{deck_id}/meta`
- `POST /shared/decks/{deck_id}/access`
- `GET /shared/decks/{deck_id}`
- `GET /shared/decks/{deck_id}/study`
- `POST /shared/decks/{deck_id}/save`
- `POST /decks/{deck_id}/save-to-library`

### Images

- `POST /images/search`
- `POST /images/import`
- `POST /images/upload`

### Quizzes

- `POST /quizzes`
- `GET /quizzes`
- `GET /quizzes/{quiz_id}`
- `GET /quizzes/{quiz_id}/edit-data`
- `PUT /quizzes/{quiz_id}`
- `DELETE /quizzes/{quiz_id}`
- `POST /quizzes/{quiz_id}/start`
- `GET /quiz-attempts/{attempt_id}`
- `PUT /quiz-attempts/{attempt_id}/answers/{question_id}`
- `POST /quiz-attempts/{attempt_id}/complete`
- `GET /quiz-attempts/{attempt_id}/results`

## Development Notes

- The backend applies lightweight schema compatibility updates on startup via `ensure_schema()`.
- The app mounts `frontend/` at `/` and `media/` at `/media`.
- Quiz pages use dedicated pretty routes such as `/quiz`, `/quiz/create`, and `/quiz/{quiz_id}/start`.
- CORS is currently open to all origins in development.
- The repository does not include a production deployment setup yet.

## Security Notes

- User passwords and deck share passwords are hashed with `bcrypt`.
- Private deck links require a password-derived access token before content is returned.
- The default `SECRET_KEY` is for local development only.
- Do not commit local secrets, `deckly.db`, or uploaded media to a public repository.

## License

No license file is included yet. Add one before publishing or accepting external contributions.
