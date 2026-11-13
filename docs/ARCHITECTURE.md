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

1. **Monorepo via `git subtree add` (no squash).** All original commits keep their hashes.
   See [GIT-HISTORY.md](GIT-HISTORY.md).
2. **Kept two separate Angular apps** instead of merging them into one Angular workspace.
   They share a lot of duplicated code (auth service, guard, interceptor, layout), but they
   target different Material majors (20 vs 21) and use different localStorage token keys.
   Merging would be a refactor with regression risk, not a consolidation. A later step could
   be an Angular workspace with a shared `projects/shared` library.
3. **No reverse proxy service.** The browser talks to the API directly on its own port. That
   is enough for local and single-host use. In production, put a TLS reverse proxy in front
   (or switch both frontends to a relative `/api` URL behind one).
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

## Security findings (action recommended)

1. **Source code and settings were downloadable over HTTP (fixed in this repo).**
   `app/urls.py` appended `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`.
   `MEDIA_URL`/`MEDIA_ROOT` were never set, so Django defaulted them to `/` and the working
   directory, and `DEBUG` was hardcoded to `True`. The result was a catch-all serving every
   file in the backend directory. Verified on the original code in Docker:
   `GET /project/settings.py` → 200, including `SECRET_KEY`. **If the Render deployment runs
   the original code, it is very likely affected.** Deploy the fix, and rotate the Django
   `SECRET_KEY` and any credentials readable from the deployed directory.
2. **Personal data in git history.** `backend/MEDIA/verifications/` (national ID front/back,
   selfies) and payment screenshots were committed in the original backend repo. They are
   untracked from now on, but still exist in history (here and on GitHub). Removing them
   needs a history rewrite (`git filter-repo --path backend/MEDIA --invert-paths`) and a
   force push, which changes every later commit hash. That's your call, so it wasn't done.
3. **The OTP is returned to the client.** `SendOTPView` includes `"otp"` (and the
   Africa's Talking username) in its JSON response, so verification can be bypassed by
   reading the response. Recommended: store the OTP server-side (Redis with a TTL is a
   natural fit now) and add a verify endpoint. This needs frontend changes, so it was not
   done here.
4. **Verification documents are publicly readable** at `/MEDIA/verifications/...` with no
   authentication (pre-existing). Consider serving them through an authenticated view.
5. `SIMPLE_JWT` is defined twice in settings. The second definition silently drops
   `ROTATE_REFRESH_TOKENS`/`BLACKLIST_AFTER_ROTATION`. Left unchanged to preserve current
   auth behaviour; merge the two dicts if rotation was intended.

## Known issues / follow-ups

- `frontend/jenga-pro` pins `@angular/material ^21` on Angular 20 (peer conflict, installed
  with `--legacy-peer-deps`). Align it to `^20.2` like fundi-pro, or upgrade the whole app to 21.
- The old `fundi_pro_backend/venv` was a Python 3.8 venv and no longer worked. Docker uses
  Python 3.11.
- `manage.py check --deploy` reports security.W004/W008/W012/W016 (HSTS, SSL redirect,
  secure session/CSRF cookies). These only make sense behind HTTPS: set
  `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
  and `SECURE_PROXY_SSL_HEADER` when you deploy behind a TLS proxy.
- `backend/e` is a committed `psql \dt` output; harmless, can be deleted.
