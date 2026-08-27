# Customizing for a new client

**Before any real deployment, close these two out — both are
currently stubbed/permissive by design so the base build works with
zero configuration, but neither is safe as-is for production:**

- [ ] **Password reset returns the raw token in the API response**
  (`POST /auth/request-password-reset`, see `backend/app/api/auth.py`).
  There's no email service wired up, so the token comes back directly
  for testability. Before going live: remove `dev_reset_token` from
  the response and actually email the token instead — otherwise
  anyone who knows an account's email can reset that password.
- [ ] **Public registration accepts any tier** (`POST /auth/register`).
  Right now the open signup form lets a caller set `tier` to
  anything, including staff/admin levels. Before going live: restrict
  tier 2+ creation to an existing staff/admin account (e.g. only
  `/accounts/{id}` PATCH by a tier-2+ caller can promote someone),
  not the public registration form.

Concrete checklist, in order, for turning this template into a real
client deployment. Nothing here is optional except where marked.

## 1. Branding — edit `client.config.json`

```json
{
  "app_name": "Whatever the client is called",
  "primary_color": "#hex",
  "tier_labels": {
    "1": "Patient",
    "2": "Staff",
    "3": "Admin"
  }
}
```

No code changes needed for this step — the backend serves it via
`GET /config/`, the frontend fetches it on load and uses it for the
app name, accent color, and how tier numbers are displayed. Tiers
themselves stay numeric everywhere in the code (permission checks,
the database) — only the *label* shown to a human changes here. Add
as many tier entries as the client actually needs; unused numbers
just never show up.

## 2. Replace the example domain entity

`Item` (`backend/app/models/item.py`, `backend/app/api/items.py`) is
a placeholder. Use `scaffold_entity.py` (see below) to generate a
real one, or copy the `Item` pattern by hand for each real entity
the client's business runs on (patients, orders, work tickets,
whatever it is).

## 3. Environment variables — `backend/.env`

Copy from `.env.example` and fill in real values:
- `DATABASE_URL` — the client's actual database
- `SECRET_KEY` — generate a real random value, never reuse the
  template's default across deployments
- `CORS_ORIGINS` — the client's actual frontend domain, not localhost

## 4. Lock down registration — **required before going live**

`/auth/register` ships open and public, accepting any tier in the
request body. That's fine for local development, genuinely unsafe
for production — anyone could register themselves a tier-3 admin
account. Before a real deployment, restrict who can create tier-2+
accounts (e.g. require an existing tier-2+ account to create one,
rather than leaving it open to self-registration).

## 5. Decide what tier 1 actually means for this client

Does tier 1 need real login (a client portal), or is it just a
record staff manage (`hashed_password` stays null)? Both work with
the same schema — this is a decision, not a code change. See the
"Accounts and tiers" section in the main README for the full pattern.

## 6. Review indexes and constraints for the client's actual scale

The base schema indexes what a typical small business needs
(foreign keys, filtered columns like `is_active`). If a client's
entity gets queried in an unusual way — filtered by a field that
isn't currently indexed — add that index before it becomes a real
performance problem, not after.

## 7. Update the README

Once the client's actual entities exist, update the main README's
structure section to reflect them instead of the generic `Item`
example.
