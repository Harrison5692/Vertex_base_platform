# Vertex Base Build

Reusable starting point for client projects — clone this, swap in the
real domain models, and you're building the actual product instead of
re-plumbing the same infrastructure every time.

Same stack as the RPM platform: **React (Vite) + FastAPI + PostgreSQL +
Docker**, with a couple of lighter-weight tooling choices layered in
(see below).

## Structure

```
backend/
  app/
    main.py          — FastAPI app entrypoint
    core/config.py    — settings, loaded from .env
    core/security.py   — password hashing, JWT issuance/verification
    core/deps.py        — get_current_account, require_min_tier(n)
    db/session.py      — async DB session
    models/           — SQLModel models (doubles as DB table + API schema)
    api/              — route handlers, one file per resource
  alembic/            — DB migrations
  tests/

frontend/
  src/
    App.jsx           — routes: /login, /register, / (protected)
    lib/auth.jsx        — auth context, token persistence
    lib/api.js          — fetch wrapper, attaches auth token automatically
    pages/             — Login, Register, Home
    components/        — Layout, ProtectedRoute

docker-compose.yml     — runs db + backend + frontend together
```

## Accounts and tiers

There's one account table, not separate client/staff tables. Every
account has a numeric `tier` instead of a fixed role — a deployment
decides what its own tiers mean. The base template's default:

- **Tier 1** — client / customer / patient / the organization itself.
  Can exist as a login-capable portal account, or as a record-only
  entry with no login at all (`hashed_password` is nullable) — a
  deployment might only need transaction history for tier-1 entities,
  never an actual portal.
- **Tier 2** — staff.
- **Tier 3+** — higher-level staff / management, open-ended. Add as
  many tiers as a given deployment actually needs; nothing in the
  code is hardcoded to a fixed number of levels.

`require_min_tier(n)` is the enforcement mechanism — see
`app/api/accounts.py` and `app/api/transactions.py` for the concrete
pattern: tier-1 accounts can only see their own record/history,
tier-2+ can see everyone's. Copy that pattern for any new resource
that needs the same self-vs-staff split.

**Registration caveat**: `/auth/register` as shipped is public and
accepts any tier in the request — fine for local development, wrong
for production. Before a real deployment, restrict who can create
tier-2+ accounts (e.g. only an existing tier-2+ account should be
able to promote someone) rather than leaving that open to self-registration.

## What's different from the RPM platform, and why

- **SQLModel instead of raw SQLAlchemy** — same engine underneath, but
  one model class serves as both the DB table and the API request/response
  shape, instead of maintaining a SQLAlchemy model *and* several separate
  Pydantic schemas per table. Less duplication when cloning this for a
  new client and adding their actual entities. Drop into raw SQLAlchemy
  for anything that needs it — they interoperate directly.
- **uv instead of plain pip** — faster installs, same dependency file.
- **Ruff instead of separate lint/format tools** — one fast tool.

Nothing else changed — same React/Vite frontend approach, same FastAPI
routing style, same Postgres, same Docker Compose orchestration.

## Running it locally

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs (auto-generated): http://localhost:8000/docs

## Using this for a new client

1. Clone this repo (or use it as a template repo on GitHub)
2. Replace `app/models/item.py` and `app/api/items.py` with the client's
   actual domain objects, following the same pattern
3. Update `frontend/src/App.jsx` and add real pages/components
4. Update `.env` with the client's actual database credentials
5. Run `alembic revision --autogenerate -m "initial schema"` then
   `alembic upgrade head` to create the real tables

## Not included yet (add as needed per client)

- Authentication (placeholder `secret_key` in config only — wire up
  real auth before handling any sensitive data)
- CI/CD
- Production deployment config (this compose setup is for local dev)
