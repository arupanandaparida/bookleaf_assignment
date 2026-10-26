# BookLeaf Author Support & Communication Portal (Python / FastAPI edition)

A two-sided web app (author portal + admin portal) where support tickets are **auto-classified, priority-scored and answered with AI-drafted replies grounded in the BookLeaf Knowledge Base**, and where authors see admin replies **live, without refreshing**.

**Stack:** Python 3.10+ · FastAPI · SQLite (stdlib `sqlite3`) · React (pre-built, in `client/`) · Server-Sent Events · Claude Haiku (OpenAI supported via env switch)

> Confidential assignment material. Keep this repository private.

---

## 1. Test credentials

| Role | Email | Password |
|---|---|---|
| Admin (ops lead) | `admin@bookleaf.com` | `Admin@123` |
| Admin (support) | `support@bookleaf.com` | `Admin@123` |
| Author (royalty never paid, above threshold) | `ananya.reddy@email.com` | `Author@123` |
| Author (book in production + ₹850 pending, below threshold) | `kavita.deshmukh@email.com` | `Author@123` |
| Author (3 books incl. one in "Cover Design") | `sneha.kulkarni@email.com` | `Author@123` |

All 10 authors in `bookleaf_sample_data.json` can log in with their listed email and `Author@123`. The login page has click-to-fill demo buttons.
On first boot the database is seeded with the 10 authors / 18 books plus 7 demo tickets built from the assignment's sample queries.

**Live URL:** _add after deploying (see §8)_

## 2. Run locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional: add ANTHROPIC_API_KEY to enable the LLM
python -m app                   # http://localhost:3001  (API + UI)
```

- **No Node needed:** the React client is already built in `client/dist` and served by FastAPI. To change the UI: `cd client && npm install && npm run dev` (Vite on :5173 proxies `/api` to :3001), then `npm run build`.
- **Interactive API docs (Swagger UI):** http://localhost:3001/api/docs
- **Tests:** `pytest` · **Reseed:** `python -m app.seed --reset`
- **No API key?** The app still works fully: classification falls back to keyword rules and drafts to per-category templates (clearly labelled in the UI). This is the same code path used when the AI API is down.

## 3. Architecture

```
app/
  main.py            app factory, security headers, serves the React build
  config.py          all settings/secrets from environment variables
  db.py, schema.sql  SQLite wrapper (WAL, FK on, RLock) + normalised schema
  security.py        bcrypt, JWT, auth dependencies (RBAC), rate limiter
  schemas.py         pydantic request validation
  errors.py          AppError + global handlers -> consistent JSON errors
  routes/            auth.py, books.py, tickets.py (tickets, admin, SSE)   <- thin HTTP layer
  services/          ticket_service.py (all business rules), book_facts.py, events.py (SSE pub/sub)
  ai/                provider.py, classifier.py, drafter.py, knowledge_base.py, fallback.py
  seed.py            loads the provided dataset
client/              React app (source + pre-built dist)
tests/               pytest integration tests
```

Key decisions:
- **Layering.** Routes only validate and delegate to `ticket_service`; the service owns business rules; `ai/` knows nothing about HTTP. The LLM sits behind one function (`provider.complete`), so swapping providers/models is configuration.
- **SQLite.** Zero setup, transactional, enough here. Normalised schema portable to PostgreSQL. **Internal notes live in their own table**, so no query serving authors can ever return them.
- **Single deployable.** FastAPI serves the built React app: no CORS surface, one URL.
- **Real-time via SSE.** One-way push is all that's needed, simpler than WebSockets, auto-reconnects. Authors only receive events for their own `authorId`; admins receive all. Events carry IDs only (no sensitive payload); the client refetches, and also on tab-visible/reconnect to self-heal. In-process pub/sub is the single-instance limit (§9).
- **Ticket creation never waits on AI.** `POST /tickets` returns `201` immediately; classification runs as a background task and pushes an update. The queue shows "Classifying…" until it lands.
- **Override precedence.** Admin edits set `*_source = 'admin'`; a late AI result never overwrites them (checked inside a transaction). "Re-run AI classification" is an explicit force.
- **Urgency ordering.** Active tickets first → Critical→Low → oldest first; tickets waiting ≥ 48h get a red edge.
- **Async where it matters.** Endpoints are `async`; CPU-bound bcrypt runs in a threadpool, and the LLM call uses `httpx.AsyncClient`, so a slow AI call never blocks other requests.

## 4. AI integration

### Model choice
**Anthropic Claude Haiku** (default `claude-haiku-5-5`, override with `AI_MODEL`): low cost and latency for a high-volume, short-context task; strong instruction-following for strict-JSON classification and for obeying tone rules; good at not inventing facts when told what it doesn't know. `AI_PROVIDER=openai` switches to `gpt-4o-mini` with no code changes.

### Two calls, each deliberately small
| Call | When | Output | Budget |
|---|---|---|---|
| **Classify + priority** (one call for both) | Background, on ticket creation (and on admin "re-run") | `{category, priority, reasoning}` JSON, `temperature 0`, `max_tokens 120` | ~450 input tokens |
| **Draft reply** | When an admin opens a ticket (cached) | Plain-text reply, `temperature 0.4`, `max_tokens 450` | ~1,100 input tokens |

### Prompt strategy
- **Classifier:** explicit categories with routing hints, a written **priority rubric** (Critical = money/legal exposure; High = BookLeaf likely at fault, ISBN errors "always at least High" per the KB; Medium; Low), JSON-only output, validated against the allowed enums. A code **guardrail** also upgrades ISBN-error tickets to High.
- **Drafter:** system prompt encoding BookLeaf's tone rules (acknowledge first, own mistakes, specific numbers, 48h timelines, end with a next step, sign off "Team BookLeaf", 110–190 words, plain text). User message is structured with `<knowledge_base>`, `<reply_pattern_for_…>`, `<facts>`, `<author_message>`, `<thread>`.
- **Grounded in real data, not just policy.** `book_facts.py` computes facts from the DB: copies × per-copy royalty = earned / paid / pending, whether pending is under the ₹1,000 threshold, **the actual next payout deadline** (quarter end + 45 days from today's date), and production-stage position (e.g. stage 3 of 9) for books in production. The prompt also lists what the model does **not** know (bank-link status, tracking, stage dates) and tells it to commit to a verification timeline instead of guessing.
- **Prompt-injection hygiene.** Author text is tagged and declared untrusted; a human always reviews the draft before sending.
- The assignment's sample query→response table is encoded as one short calibration pattern per category.

### Cost awareness
- Only **core KB + the one section for the ticket's category** is sent, never the whole KB.
- Facts are scoped to the referenced book (account-level tickets: one line per book).
- Thread history: last 4 messages, each capped at 600 chars; the original message is never duplicated.
- Inputs are length-capped; `max_tokens` is tight.
- **Drafts are lazy and cached** per ticket (invalidated only when the author adds a message); concurrent opens are de-duplicated in flight. Classification runs once per ticket.
- Every call is logged to `ai_calls` (model, tokens, latency, errors); totals show on the admin dashboard.
- Next step (not implemented): Anthropic prompt caching for a stable prefix.

### Graceful degradation
`provider.complete` handles: missing key → timeout (15s) → one retry with backoff on 429/5xx/network errors → **circuit breaker** (3 consecutive failures pause AI for 60s). On any failure:
- classification → keyword/regex rules (tagged `rules` in the UI),
- draft → per-category template following the KB tone (tagged "AI unavailable: template loaded"),
- the ticket is **always created** and an admin can always write a reply manually.
Invalid/off-schema model output is treated as a failure and falls back the same way.

### Secrets
Keys are read only in `app/config.py` from environment variables; never sent to the client, never logged; `.env` is git-ignored. The frontend has no AI code, it only calls the REST API.

## 5. API reference
Interactive docs: **`/api/docs`** (Swagger UI) and `/api/openapi.json`. Summary:

Base path `/api`, JSON in/out. Auth: `Authorization: Bearer <JWT>` from `POST /auth/login` (SSE also accepts `?token=` since `EventSource` can't set headers).
Errors are always `{ "error": { "code", "message", "details?" } }` with codes `VALIDATION_ERROR` 400 · `BAD_REQUEST` 400 · `UNAUTHORIZED` 401 · `FORBIDDEN` 403 · `NOT_FOUND` 404 · `RATE_LIMITED` 429 · `INTERNAL_ERROR` 500. Validation errors list `details: [{field, message}]`.

| Method & path | Role | Purpose |
|---|---|---|
| `GET /health` | public | Liveness |
| `POST /auth/login` | public (rate-limited) | `{email, password}` → `{token, user}` |
| `GET /auth/me` | any | Current user |
| `GET /meta` | any | Allowed categories, priorities, statuses |
| `GET /books` | any | Author: own books only (query string can't widen it). Admin: all, optional `?authorId=` |
| `GET /books/{id}` | any | One book (author: 404 if not theirs) |
| `GET /tickets` | any | Author: own. Admin: all with `status, category, priority, assigned=me\|unassigned, authorId, from, to (YYYY-MM-DD), q, limit, offset`; sorted by urgency |
| `POST /tickets` | author | `{bookId?, subject (5–150), description (20–5000), attachments?[{name,size}]}` → 201; classification is async |
| `GET /tickets/{id}` | any | Ticket + messages. Admin also gets `notes`, `aiDraft`, priority, sources. Others' tickets → 404 |
| `PATCH /tickets/{id}` | admin | Any of `status, category, priority, assignedTo ("me"\|adminId\|null)`; category/priority edits are marked `admin` |
| `POST /tickets/{id}/messages` | any | `{body, status?}`. Admin reply (auto-assigns, Open→In Progress by default). Author follow-up reopens a Resolved ticket; Closed rejects |
| `POST /tickets/{id}/notes` | admin | Internal note, never visible to authors |
| `POST /tickets/{id}/draft?regenerate=` | admin | Cached or fresh AI draft `{draft:{text, source: ai\|template, stale}}` |
| `POST /tickets/{id}/reclassify` | admin | Re-run AI classification (forces) |
| `GET /admin/stats` | admin | Queue counts + AI usage/health |
| `GET /admin/admins` | admin | Admin users (for assignment) |
| `GET /events` | any | SSE stream of `ticket` events `{type, ticketId, authorId}` |

Security: bcrypt hashes, JWT with expiry, user re-loaded from the DB on every request, identical error for unknown email vs wrong password, rate limits (login 10/min, ticket creation, AI endpoints), CSP and other security headers, request-body validation on every write.

## 6. Edge cases handled
- Books **in production** (BK013, BK015): shown with stage status, no fake zero royalties/MRP; selectable in the ticket dropdown; AI facts describe the stage.
- **Zero payouts** (Ananya: ₹2,546 pending, never paid) vs **below-threshold** (Kavita: ₹850): different UI notes and different AI facts (roll-over vs possibly overdue).
- Fully paid books (₹0 pending), `null` payout dates, authors with no tickets (empty states).
- Authors requesting others' books/tickets → 404; authors on admin routes → 403.
- Admin overrides survive late AI results.

## 7. Tests
`pytest` runs 8 integration tests against the real FastAPI app with an in-memory DB and the outbound AI call mocked: auth, RBAC, data isolation, validation, the full ticket lifecycle (classify → override → draft → cache hit → reply → author sees it, never notes → reopen/closed rules), prompt contents (only the relevant KB section), AI-outage fallback, queue ordering/filters, JSON 404.

## 8. Deploying
`render.yaml` is a Render Blueprint (`pip install -r requirements.txt` → `uvicorn app.main:app …`); a `Dockerfile` is included for Railway/Fly/VPS. Set `ANTHROPIC_API_KEY` in the host dashboard (optional); `JWT_SECRET` is auto-generated on Render. The free tier's disk is ephemeral so the DB reseeds on restart; attach a disk and set `DB_PATH` to persist. `client/dist` is committed so no Node build step is needed.

## 9. Known limitations / next steps
- **Real LLM calls were not exercised against a live API in development** (no key available): the provider is tested with mocked responses. After adding a key, open a ticket and check the admin dashboard's AI call/failure counters. If the default model id isn't enabled on your account, set `AI_MODEL`.
- Attachments are UI-only (names recorded, no storage). Next: S3-compatible upload with signed URLs + virus scan.
- SSE uses in-process pub/sub and one shared SQLite connection (single instance). Next: Redis pub/sub + PostgreSQL.
- No email notification on reply, password reset, or admin user management.
- No SLA timers, canned replies, or per-draft thumbs up/down (which would give a measured accuracy and an eval set).
- Bank-link status and per-platform sales aren't in the dataset, so the AI is told not to claim them.
