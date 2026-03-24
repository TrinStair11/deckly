# TrinDeckly

TrinDeckly is a full-stack flashcard and spaced-repetition app built with FastAPI, SQLite, and a static Bootstrap frontend. It supports account-based learning, deck authoring, shared deck access, interval review, image-backed cards, and a dark-mode study experience optimized for focused repetition.

The repository includes both the backend API and the shipped frontend. Running the FastAPI app serves the API, static media, and the browser UI from a single process.

## Features

- JWT-based authentication with registration, login, profile lookup, email change, and password change.
- Deck management: create, edit, delete, reorder cards, and attach images to cards.
- Study modes: review all, limited review, interval review, and test mode.
- Spaced repetition state stored per user and per card.
- Public and private deck sharing.
- Password-protected private deck access via short-lived access token.
- Save shared decks into a personal library.
- Image workflows:
  - search via Openverse
  - import external images
  - upload local images as base64 payloads
- Premium dark-mode frontend for dashboard, deck editor, settings, study hub, and fullscreen review.

## Tech Stack

- Backend: FastAPI, SQLAlchemy 2.x, Pydantic 1.x
- Auth: JWT (`python-jose`), `bcrypt`
- Database: SQLite
- HTTP client: `httpx`
- Frontend: static HTML + Bootstrap 5 + Bootstrap Icons
- Tests: `pytest`, `pytest-cov`

## Project Structure

```text
backend/
  auth.py                Auth helpers, JWT, password hashing
  db.py                  SQLAlchemy engine, schema bootstrap/migrations
  main.py                FastAPI app, API routes, static mounts
  models.py              Database models
  schemas.py             Request/response schemas
  spaced_repetition.py   Review/session scheduling logic
  time_utils.py          UTC-safe datetime helpers

frontend/
  index.html             Dashboard
  deck.html              Deck editor / deck management UI
  study.html             Study hub and active review UI
  settings.html          Account settings UI

tests/
  test_auth.py
  test_db.py
  test_main.py
  test_models.py
  test_schemas.py
```

## Quick Start

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
uvicorn backend.main:app --reload
```

Open:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

On first start, the SQLite database file `deckly.db` is created automatically and the schema bootstrap runs on import.

## Configuration

The app works locally without any extra setup, but the following environment variables are supported:

```bash
export SECRET_KEY="replace-this-in-real-environments"
export OPENVERSE_API_URL="https://api.openverse.org/v1/images/"
```

Notes:

- `SECRET_KEY` defaults to a development value in code. Override it outside local development.
- `OPENVERSE_API_URL` is optional; the default points to the public Openverse API.
- Uploaded and imported images are stored in the local `media/` directory and served from `/media/...`.

## Running Tests

Use `PYTHONPATH=.` so the test runner can import the `backend` package correctly:

```bash
PYTHONPATH=. pytest -q
```

Current test status in this workspace:

- 45 tests passing
- total coverage: 86.87%

## API Overview

### Authentication

- `POST /register`
- `POST /login`
- `GET /me`
- `PUT /account/email`
- `PUT /account/password`

### Decks

- `POST /decks`
- `GET /decks`
- `GET /decks/{deck_id}`
- `PUT /decks/{deck_id}`
- `DELETE /decks/{deck_id}`

### Cards

- `POST /decks/{deck_id}/cards`
- `PUT /cards/{card_id}`
- `DELETE /cards/{card_id}`
- `PUT /decks/{deck_id}/cards/reorder`
- `GET /cards`

### Study and Review

- `GET /decks/{deck_id}/study/session`
- `GET /decks/{deck_id}/study`
- `GET /decks/{deck_id}/progress`
- `POST /reviews/submit`
- `POST /cards/{card_id}/review`

### Sharing

- `GET /shared/decks/{deck_id}/meta`
- `POST /shared/decks/{deck_id}/access`
- `GET /shared/decks/{deck_id}`
- `GET /shared/decks/{deck_id}/study`
- `POST /shared/decks/{deck_id}/save`

### Images

- `POST /images/search`
- `POST /images/import`
- `POST /images/upload`

## Frontend Notes

- The frontend is served directly by FastAPI using `StaticFiles`.
- The dashboard, deck editor, study hub, and settings page are in `frontend/`.
- Authentication entry is centralized in the top-right profile/avatar menu.
- Shared private decks require a password flow before deck content is returned.
- Fullscreen review mode is handled in the browser on top of the study session state.

## Security Notes

- User passwords are hashed with `bcrypt`.
- Private deck passwords are hashed before storage.
- Private shared deck content is gated by backend access checks.
- The default `SECRET_KEY` is suitable only for local development.
- Do not commit `deckly.db`, `media/`, or local secrets to a public repository.

## Development Notes

- The repository currently uses SQLite for persistence.
- Schema compatibility helpers live in `backend/db.py`.
- The backend serves the frontend and media mounts from `backend/main.py`.
- Local runtime artifacts are intentionally ignored via `.gitignore`.

## License

No license file is included yet. If you intend to publish or accept contributions, add an explicit license before making the repository public.
