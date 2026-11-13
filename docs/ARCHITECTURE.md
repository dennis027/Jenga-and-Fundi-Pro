# Architecture

## Overview

```
                    Browser
        ┌──────────────┼──────────────────┐
        │ :4200        │ :4300            │ :8000  (XHR/fetch, JWT Bearer)
        ▼              ▼                  ▼
  ┌───────────┐  ┌───────────┐      ┌──────────────┐  ── web network (egress) ──►  Safaricom Daraja,
  │ fundi-pro │  │ jenga-pro │      │   backend    │                               SMTP, Africa's Talking
  │ Node SSR  │  │ Node SSR  │      │ Django+gunic.│
  └───────────┘  └───────────┘      └──────┬───────┘
                                           │  data network (internal: no egress, no published ports)
                                   ┌───────┴────────┐
                                   ▼                ▼
                             ┌──────────┐     ┌──────────┐
                             │ postgres │     │  redis   │
                             └──────────┘     └──────────┘
```

- Both Angular apps prerender **every** route at build time (`RenderMode.Prerender` on `**`)
  and call the API **from the browser only**. The Node/Express SSR containers serve static,
  prerendered pages and never talk to the backend. That's why the frontends are on the `web`
  network only and why the API URL is a build-time argument (`PUBLIC_API_URL`).
- The backend is the only service on both networks. It needs internet egress for M-Pesa,
  SMTP and SMS, and it is the only service that reaches Postgres and Redis.
- Authentication: SimpleJWT access/refresh tokens in `localStorage`
  (`fundi_*_token` keys in fundi-pro, `jenga_*_token` in jenga-pro). Both portals use the same
  API and user model; the portal decides which features a user sees.

## Component responsibilities

| Component | Responsibilities |
|---|---|
| `backend/project/` | Settings (all env-driven), root URLs, `health.py` (`/healthz/`: DB + Redis check) |
| `backend/app/` | Models (User, Gig, Organization, JobType, Payment, VerificationRequest, M-Pesa transactions…), DRF views, email templates, signals (default job types per organization) |
| `frontend/fundi-pro/` | Worker portal: dashboard, log gigs, search gigs, work history, proof of payment, credit score, verification, analytics |
| `frontend/jenga-pro/` | Contractor portal: dashboard, all/verify gigs, manage workers, sites (organizations), gig types, M-Pesa payments, reports, analytics |

## Decisions

1. **Monorepo via `git subtree add` (no squash).** All original commits are kept. Frontend
   hashes are unchanged. Backend hashes changed when uploaded personal data was purged
   from history. See [GIT-HISTORY.md](GIT-HISTORY.md).
2. **Kept two separate Angular apps** instead of merging them into one Angular workspace.
   They share a lot of duplicated code (auth service, guard, interceptor, layout), but they
   use different localStorage token keys and different routes.
   Merging would be a refactor with regression risk, not a consolidation. A later step could
   be an Angular workspace with a shared `projects/shared` library.
3. **Reverse proxy only in production.** In the default and dev stacks the browser talks to
   the API directly on its own port. `docker-compose.prod.yml` adds Caddy (automatic Let's
   Encrypt) with one hostname per component. Caddy was chosen over nginx because it handles
   certificate issuance and renewal itself, with no certbot sidecar or cron.
4. **Redis is used for cache + sessions, not a job queue.** The only Redis-shaped needs in
   the current code are the M-Pesa token (requested on every STK push before) and sessions.
   Emails (registration, password reset) are still sent synchronously in the request. If
   that becomes a latency problem, add `django-rq` with a `worker` service on the same
   Redis. That was deliberately not done, to avoid a new service and dependency without
   a demonstrated need.
5. **Migrations run on container start** (`docker-entrypoint.sh`). That's simple for a
   single replica. With several replicas, set `RUN_MIGRATIONS=0` and migrate in a one-off job.
6. **Uploads** go to the `media` volume (`MEDIA_ROOT=/data/media`). Upload paths and URLs
   (`/MEDIA/...`) are unchanged. Django serves them when `SERVE_MEDIA=True`. At scale, serve
   them from the reverse proxy or object storage instead.
7. **Render: Docker everywhere, database on Neon.** `render.yaml` deploys the same Dockerfiles
   as Compose. The existing Neon database is kept (no data migration, no Render Postgres).
   The backend entrypoint starts as root only to `chown` the media mount (Render disks
   and new volumes are root-owned), then drops to the `app` user with `setpriv`. A
   first-in-chain `HealthCheckMiddleware` answers `/healthz/` before host validation and
   SSL redirects, because platform health checkers use internal Host headers.
8. **Views split by area.** `app/views/` (auth, phone, payments, verification, gigs, reports,
   fundi_dashboard, contractor_dashboard, certificate, ratings, ussd) replaces the 4,000-line
   `views.py`. The package re-exports everything, so imports and URLs didn't change.

## Changes made to existing code during consolidation

All of these keep existing behaviour and API contracts unless noted.

| File | Change | Why |
|---|---|---|
| `backend/project/settings.py` | `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, CORS, CSRF, `MPESA_BASE_URL`, `FRONTEND_APP_URL`, `MEDIA_ROOT` read from env | They were hardcoded (`DEBUG=True`, `ALLOWED_HOSTS=['*']`, a committed secret key). **Behaviour change:** `CORS_ALLOW_ALL_ORIGINS` now defaults to `False`; allowed origins come from `CORS_ALLOWED_ORIGINS`. |
| `backend/project/settings.py` | Redis cache + `cached_db` sessions when `REDIS_URL` is set; console `LOGGING` | Redis integration; errors were invisible in `docker logs` with `DEBUG=False` |
| `backend/project/settings.py` | Removed duplicate `SecurityMiddleware` entry and a dead first block of `DEBUG/SECRET_KEY/ALLOWED_HOSTS` that was immediately overwritten | Duplicates |
| `backend/app/urls.py` | Media served only under `/MEDIA/`, only if `SERVE_MEDIA` | **Security fix**, see below |
| `backend/app/views.py` | `get_access_token()` caches the Daraja token; Daraja URLs use `settings.MPESA_BASE_URL`; 30 s timeout on the token request | Redis integration; sandbox URL was hardcoded |
| `backend/project/health.py`, `project/urls.py` | New `/healthz/` | Docker health check |
| `backend/requirements.txt` | `+ redis==5.2.1` | Client for Django's built-in Redis cache backend |
| `frontend/*/.gitignore` | `src/environments/` no longer ignored; files committed | A fresh clone could not build (`fileReplacements` reference them). They contain only public URLs. |
| `backend/app/otp.py`, `views.py`, `urls.py` | OTP stored hashed in Redis with TTL, rate limits and attempt lockout; new `POST /verify-otp/`; code removed from the `/send-otp/` response and error responses | **Security fix / API change**, see below |
| `backend/app/views.py` | OTP and password-reset codes generated with `secrets` instead of `random` | `random` is not cryptographically secure |
| `backend/project/settings.py` | Env-driven HTTPS settings (`SECURE_SSL_REDIRECT`, HSTS, secure cookies, `X-Forwarded-Proto/For`) | Used by `docker-compose.prod.yml` |
| `backend/app/tests.py` | 10 tests (was empty) | OTP, M-Pesa cache, health, media, source-exposure regression |
| `frontend/jenga-pro/package.json` | `@angular/material` `^21.0.3` → `^20.2.14`, `@angular/cdk ^20.2.14` added (same as fundi-pro) | Material 21 requires Angular 21; installs needed `--legacy-peer-deps`. Now a strict `npm ci` works. |

## Security findings

1. **Source code and settings were downloadable over HTTP (fixed in this repo).**
   `app/urls.py` appended `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`.
   `MEDIA_URL`/`MEDIA_ROOT` were never set, so Django defaulted them to `/` and the working
   directory, and `DEBUG` was hardcoded to `True`. The result was a catch-all serving every
   file in the backend directory. Verified on the original code in Docker:
   `GET /project/settings.py` → 200, including `SECRET_KEY`. **If the Render deployment runs
   the original code, it is very likely affected.** Deploy the fix, and rotate the Django
   `SECRET_KEY` and any credentials readable from the deployed directory.
2. **Personal data in git history (purged from this repo).** National ID photos, selfies,
   payment screenshots (`MEDIA/`) and OCR scratch images (`temp/`) had been committed in the
   original backend repo. They were removed from **all of this repository's history** with
   `git filter-repo` (see [GIT-HISTORY.md](GIT-HISTORY.md)). **The original GitHub repo
   `dennis027/jenga-backend` still contains them.** Removing them there needs a force push
   of rewritten history, plus a GitHub Support request to purge cached views and forks.
3. **The OTP was returned to the client (fixed).** `/send-otp/` returned the code, the raw
   gateway response and the Africa's Talking username, and its error path echoed the SMS text
   containing the code. Any caller could skip phone verification. Codes are now stored
   server-side and checked via `/verify-otp/`. This is an **API change** for clients that
   compared the code locally; see the README for the temporary compatibility flag.
4. **Verification documents were publicly readable (fixed).** `/MEDIA/verifications/...` is
   now served only to signed-in staff or through short-lived signed links (`app/media.py`).
5. **Credit scores and trust flags could be forged (fixed).** The profile API accepted
   `credit_score`/`is_verified`, because a duplicate `UserProfileSerializer` without read-only
   fields shadowed the first one. Any user could verify any gig, complete any gig, and approve any
   ID (including their own). Unauthenticated, forged M-Pesa success callbacks were stored. Gigs
   with client phone numbers, all users' personal data, all M-Pesa transactions and platform
   reports were readable by every signed-in user. All of this was reproduced locally and fixed,
   and each case has a regression test (`app/tests_trust.py`). A read-only audit of the live Neon data
   found no inflated scores and no gig verified by anyone but the site's owner.
6. **ID rejection locked users out (fixed).** ID review wrote `is_verified`, which login uses as
   the email-confirmed flag. Identity status now lives on `current_verification` (`id_verified`).
7. `SIMPLE_JWT` is defined twice in settings. The second definition silently drops
   `ROTATE_REFRESH_TOKENS`/`BLACKLIST_AFTER_ROTATION`. Left unchanged to preserve current
   auth behaviour; merge the two dicts if rotation was intended.

## Known issues / follow-ups

- The old `fundi_pro_backend/venv` was a Python 3.8 venv and no longer worked. Docker uses
  Python 3.11.
- In production mode, `manage.py check --deploy` reports only security.W021
  (`SECURE_HSTS_PRELOAD`). It's opt-in on purpose: preload is close to irreversible.
- Phone OTP enforcement exists (`REQUIRE_PHONE_OTP`) but is off until the portals and the mobile
  app have an OTP step.
- **Deferred: shared Angular library.** The portals share 26 identical files (~1,900 lines) and ~10
  near-identical ones (auth service, interceptor, login/register, profile), which differ in token key
  names and branding. Extracting them means building both apps from a common context. That
  changes both Dockerfiles, Compose, CI and both live Render services, for no user-facing change,
  so it's left for a dedicated change.
- Swahili translation (Angular i18n for both portals) is not done.
- Some analytics views have no serializer, so `/api/docs/` lists them without typed responses.
- Certificate links can't be revoked before expiry. A per-user nonce would allow that.
- `backend/e` is a committed `psql \dt` output; harmless, can be deleted.
