# Deckly

Deckly is a full-stack learning app built around two workflows:

- flashcard decks with spaced repetition, sharing, progress tracking, and study sessions
- standalone quizzes with authored questions, attempts, scoring, results, and review

The backend is a single FastAPI app that serves the API, uploaded media, and the bundled frontend.
Runtime and tests both use PostgreSQL.

## What The Project Does

### Decks

- create, edit, delete, and reorder decks and cards
- store card images from upload or external import
- track per-user spaced repetition state
- run study sessions in `interval`, `limited`, and `review_all` modes
- save other users' decks into a personal library
- share public decks by link
- protect private decks with a password

### Quizzes

- create and edit quizzes with multiple questions and options
- start attempts and save answers
- complete attempts and calculate results
- open result and review pages
- block quiz mutation while attempts are still in progress

### Security And Hardening

- user passwords are hashed with `bcrypt`
- private deck passwords are hashed and never returned
- JWT signing secret is mandatory
- auth uses an HTTP-only cookie for the main session
- private shared decks require a separate share token in `X-Deck-Access-Token`
- login and private deck access are rate-limited in memory
- image import rejects non-HTTPS URLs, loopback/private hosts, invalid redirects, and oversized payloads

## Stack

- Backend: FastAPI
- ORM: SQLAlchemy 2.x
- Validation: Pydantic 1.x
- Database: PostgreSQL
- Auth: `python-jose`, `bcrypt`
- HTTP client: `httpx`
- Env loading: `python-dotenv`
- Frontend: static HTML + vanilla JavaScript
- Tests: `pytest`, `pytest-cov`

## Repository Layout

```text
backend/
  auth.py                Auth, cookies, JWT helpers
  config.py              Auto-loading .env from repo root
  db.py                  Engine, sessions, lightweight schema bootstrap
  main.py                Main API routes for auth, decks, study, sharing, images
  models.py              SQLAlchemy models
  quiz_router.py         Quiz routes
  quizzes.py             Quiz domain logic
  schemas.py             Pydantic schemas
  spaced_repetition.py   Study session and scheduling logic
  time_utils.py          UTC-safe datetime helpers

frontend/
  pages/                Page entrypoints and page-specific assets
  shared/               Shared frontend scripts

docker/
  entrypoint.sh         Container startup wrapper

Dockerfile              App image build
compose.yaml            Local container orchestration

tests/
  test_auth.py
  test_db.py
  test_hardening.py
  test_main.py
  test_models.py
  test_quiz.py
  test_schemas.py
```

## Requirements

- Python 3.10+
- `pip`

## Quick Start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

Preferred:

```bash
pip install -e ".[dev]"
```

Fallback:

```bash
pip install -r requirements.txt
```

### 3. Create `.env`

The app auto-loads `.env` from the repository root.

```bash
cp .env.example .env
```

Generate a real secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated value into `SECRET_KEY` inside `.env`.

### 4. Start PostgreSQL

Make sure PostgreSQL is running and the database from `.env` exists.

Example for a local instance:

```bash
createdb deckly
```

### 5. Run the app

```bash
uvicorn backend.main:app --reload
```

Open:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`
- Quiz UI: `http://127.0.0.1:8000/quiz`

## Docker

### 1. Prepare `.env`

```bash
cp .env.example .env
```

Set a real `SECRET_KEY` in `.env`.

### 2. Build and run

```bash
docker compose up --build
```

Open:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

### 3. Development mode with live reload

Use the base compose file together with the dev override:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

In this mode:

- backend code from `./backend` is bind-mounted into the container
- frontend assets from `./frontend` are bind-mounted into the container
- `uvicorn` runs with `--reload` for Python changes in `backend/`
- frontend HTML, CSS, and JS changes are served directly from disk after a browser refresh

You only need another `--build` when image-level inputs change, for example:

- `Dockerfile`
- `pyproject.toml`
- `requirements.txt`

Normal backend and frontend code edits do not require rebuilding the image in dev mode.

### 4. Stop

```bash
docker compose down
```

If you also want to remove persisted PostgreSQL and uploaded media volumes:

```bash
docker compose down -v
```

## Environment Variables

Minimal required config:

```env
SECRET_KEY=replace-with-a-random-secret
```

Default local template:

```env
DATABASE_URL=postgresql+psycopg://deckly:deckly@127.0.0.1:5432/deckly
APP_HOST=127.0.0.1
APP_PORT=8000
POSTGRES_DB=deckly
POSTGRES_USER=deckly
POSTGRES_PASSWORD=deckly
CORS_ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
OPENVERSE_API_URL=https://api.openverse.org/v1/images/
MAX_IMAGE_DOWNLOAD_BYTES=5242880
MAX_IMAGE_UPLOAD_BYTES=5242880
IMAGE_REDIRECT_LIMIT=3
LOGIN_RATE_LIMIT=5
DECK_ACCESS_RATE_LIMIT=5
RATE_LIMIT_WINDOW_SECONDS=600
ACCESS_COOKIE_SECURE=false
ACCESS_COOKIE_SAMESITE=lax
```

Notes:

- `SECRET_KEY` has no fallback. Without it the app must not start.
- `.env` is loaded automatically on import.
- runtime defaults to PostgreSQL on `127.0.0.1:5432`
- SQLite is not supported anymore; startup rejects `sqlite:///...` database URLs.
- `APP_HOST` and `APP_PORT` are used by the Docker entrypoint and can also be reused for local shell scripts.
- CORS defaults to localhost only.
- image limits are in bytes
- rate limiting is in-memory, so it is process-local

Docker-specific overrides in `compose.yaml`:

- `DATABASE_URL=postgresql+psycopg://...@db:5432/...`
- PostgreSQL data is persisted in the `postgres_data` named volume
- named volume for uploads at `/app/media`

## Running Tests

```bash
pytest
```

Tests create and destroy temporary PostgreSQL databases automatically. By default they connect to:

```env
TEST_DATABASE_URL=postgresql+psycopg://deckly:deckly@127.0.0.1:5432/deckly_test_bootstrap
```

Override `TEST_DATABASE_URL` if your local PostgreSQL runs elsewhere.
The test user must also have permission to create and drop databases.

Coverage is enforced by `pytest.ini`.

Current backend test status after the latest hardening pass:

- `91 passed`
- coverage above `85%`

## Auth Model

`POST /login` returns a token payload for compatibility, but the main app flow uses an HTTP-only cookie.

Main authenticated requests:

- browser frontend uses the cookie automatically
- direct API clients can still use Bearer auth

Private deck sharing is separate from account auth:

1. call `POST /shared/decks/{deck_id}/access` with the deck password
2. receive a short-lived share token
3. send that token in `X-Deck-Access-Token` to shared/private deck endpoints

## API Overview

### Auth

- `POST /register`
- `POST /login`
- `POST /logout`
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

### Study

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

## Important Behavior

- deck and quiz validation strips whitespace and rejects blank required fields
- private saved decks still require a valid share token after visibility changes
- deck list/detail GET routes no longer create progress rows just by reading
- batch deck creation preserves card order correctly
- image upload validates actual file signature instead of trusting filename
- quiz updates and deletes are blocked when there are active attempts

## Local Data

Runtime artifacts created locally:

- `media/`
- `.env`
- pytest and coverage caches

These files should not be committed.

## Current Limitations

- database migrations are still lightweight compatibility updates, not full Alembic migrations
- PostgreSQL is now the main runtime database, but migrations are still lightweight bootstrap logic
- rate limiting is local-memory only
- the frontend is static and intentionally simple

## License

No license file is included yet.
