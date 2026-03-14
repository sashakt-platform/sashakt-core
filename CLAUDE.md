# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sashakt is an assessment/testing platform built with FastAPI, SQLModel, and PostgreSQL. Based on the full-stack-fastapi-template. The backend lives entirely in `backend/`.

## Development Environment

Docker-based development. Start everything with:
```bash
docker compose watch
```

To shell into the backend container:
```bash
docker compose exec backend bash
```

For local dev without Docker (from `backend/`):
```bash
uv sync
uv run fastapi dev app/main.py
```

## Common Commands

### Tests (run from project root)
```bash
# Full test suite with coverage (builds and runs Docker stack)
bash scripts/test.sh

# Run tests inside an already-running stack
docker compose exec backend bash scripts/tests-start.sh

# Run a single test file or test
docker compose exec backend bash -c "pytest app/tests/path/to/test_file.py -x"

# Run a specific test by name
docker compose exec backend bash -c "pytest app/tests/ -k 'test_name' -x"
```

### Linting & Type Checking (run inside container or with venv active, from `backend/`)
```bash
# All checks (mypy + ruff lint + ruff format check)
bash scripts/lint.sh

# Individual tools
mypy app
ruff check app
ruff format app --check
ruff format app          # auto-fix formatting
```

### Pre-commit (from project root)
```bash
uv run pre-commit run --all-files
```

### Database Migrations
```bash
# Create a new migration (from project root)
bash scripts/create-migrations.sh -m "describe change"

# Run migrations
bash scripts/run-migrations.sh

# Sync migration files from container to host
bash scripts/sync-migrations.sh

# Or manually inside the container:
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Architecture

### Backend Structure (`backend/app/`)
- **`main.py`** — FastAPI app entry point
- **`api/main.py`** — API router aggregation
- **`api/routes/`** — Route handlers (candidate, certificate, entity, form, location, login, organization, permissions, providers, question, roles, tag, test, users, utils)
- **`api/deps.py`** — Dependency injection (`SessionDep`, `CurrentUser`, `permission_dependency()`)
- **`models/`** — SQLModel models (define both DB tables and Pydantic schemas)
- **`crud/`** — Database CRUD operations
- **`services/`** — Business logic (data_sync, certificate_tokens, google_slides)
- **`core/config.py`** — Pydantic Settings loaded from `.env`
- **`core/security.py`** — JWT token creation/validation, password hashing
- **`core/db.py`** — Database engine and session setup
- **`core/permissions.py`** / **`core/roles.py`** — Permission and role initialization
- **`alembic/`** — Database migration versions
- **`tests/`** — Pytest test suite with fixtures in `conftest.py`

### Auth & Authorization
- JWT tokens (HS256) with OAuth2 password bearer flow
- Role-based access: super_admin, system_admin, state_admin, test_admin, candidate
- Use `permission_dependency()` from `api/deps.py` for route-level access control

### Key Patterns
- Always use top-level imports (not inline/local imports)
- SQLModel IDs are typed `int | None`. After `db.commit()` + `db.refresh()`, the ID is non-None at runtime but mypy sees `int | None`. Use `assert obj.id is not None` when passing to functions expecting `int`.
- Always run `mypy app` after code changes (inside Docker: `docker compose exec backend bash -c "mypy app"`)
- mypy is configured with `strict = true`
- ruff targets Python 3.10, excludes alembic directory

### Testing
- Tests use transactional rollback for isolation
- Fixtures provide authenticated clients for each role (superuser, systemadmin, stateadmin, testadmin, candidate)
- Pass extra pytest args via: `docker compose exec backend bash scripts/tests-start.sh -x -k "test_name"`

## URLs (Local Development)
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Adminer (DB admin): http://localhost:8080
- Traefik UI: http://localhost:8090
- MailCatcher: http://localhost:1080
- Health check: http://localhost:8000/api/v1/utils/health-check/
