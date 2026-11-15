# Fundi / Jenga Pro

Monorepo for the Fundi / Jenga Pro platform: construction workers (*fundis*)
log gigs, and contractors verify them, manage sites and workers, and pay via
M-Pesa.

| Component | Path | Stack | Purpose |
|---|---|---|---|
| **Backend API** | [backend/](backend/) | Django 4.2, DRF, SimpleJWT, PostgreSQL, Redis | REST API, auth, M-Pesa STK push, SMS OTP, OCR, reports |
| **Fundi Pro** | [frontend/fundi-pro/](frontend/fundi-pro/) | Angular 20 (SSR / prerender), Material 20 | Worker portal: log gigs, work history, credit score, payments |
| **Jenga Pro** | [frontend/jenga-pro/](frontend/jenga-pro/) | Angular 20 (SSR / prerender), Material 20 | Contractor portal: verify gigs, manage workers/sites, reports, M-Pesa |

**Live:** [Fundi Pro](https://dennis027.github.io/Jenga-and-Fundi-Pro/fundi-pro/) (workers) ·
[Jenga Pro](https://dennis027.github.io/Jenga-and-Fundi-Pro/jenga-pro/) (contractors) — on GitHub Pages ·
[API](https://fundi-jenga-api.onrender.com/api/docs/) on Render. The free API sleeps when idle, so
the first request after a quiet spell can take about a minute. Test logins are under
[Test accounts](#test-accounts).

## Screenshots

Taken from a local stack loaded with the demo data (`seed_demo_data`). Click any image for full size.

### Jenga Pro (contractors)

| **Dashboard** | **Notifications** |
|---|---|
| [![Dashboard](docs/screenshots/jenga-dashboard.png)](docs/screenshots/jenga-dashboard.png) | [![Notifications](docs/screenshots/jenga-notifications.png)](docs/screenshots/jenga-notifications.png) |
| Gigs waiting for verification, quick actions, site switcher. | Things that need you now, then recent events with *Mark all read*. |
| **Verify gigs** | **Reject with a reason** |
| [![Verify gigs](docs/screenshots/jenga-verify-gigs.png)](docs/screenshots/jenga-verify-gigs.png) | [![Reject a gig](docs/screenshots/jenga-reject-gig.png)](docs/screenshots/jenga-reject-gig.png) |
| Select several and verify them in one go. Each adds +5 to the worker's score. | The gig is removed and the worker is told why. |
| **Find workers by trade** | **Applicants and crew invites** |
| [![Find workers](docs/screenshots/jenga-workers-find.png)](docs/screenshots/jenga-workers-find.png) | [![Applicants](docs/screenshots/jenga-job-applicants.png)](docs/screenshots/jenga-job-applicants.png) |
| Trades, day rate, availability, score and rating. Star a worker to add them to *My crew*. | Accept or decline applicants, or invite people from your crew. |
| **Payroll** | **Labour budgets** |
| [![Payroll](docs/screenshots/jenga-payroll.png)](docs/screenshots/jenga-payroll.png) | [![Budgets](docs/screenshots/jenga-budgets.png)](docs/screenshots/jenga-budgets.png) |
| Agreed pay, gig days and days checked in per worker. Downloads as CSV. | Spend against budget per site; red when over. |
| **Site ratings** | **Site safety** |
| [![Site ratings](docs/screenshots/jenga-site-ratings.png)](docs/screenshots/jenga-site-ratings.png) | [![Safety](docs/screenshots/jenga-safety.png)](docs/screenshots/jenga-safety.png) |
| What workers say about your sites, and how often they were paid on time. | Injuries, near misses and hazards reported at your sites. |
| **Activity** | **Dark mode** |
| [![Activity](docs/screenshots/jenga-activity.png)](docs/screenshots/jenga-activity.png) | [![Dark mode](docs/screenshots/jenga-dark.png)](docs/screenshots/jenga-dark.png) |
| A dated record of verifications, rejections, hires and reports. | Follows the system setting, or switch from the sidebar. |

### Fundi Pro (workers)

| **Dashboard** | **Kiswahili** |
|---|---|
| [![Dashboard](docs/screenshots/fundi-dashboard.png)](docs/screenshots/fundi-dashboard.png) | [![Kiswahili](docs/screenshots/fundi-kiswahili.png)](docs/screenshots/fundi-kiswahili.png) |
| Credit score, gigs to finish, daily site check-in. | Switch language from the user menu. |
| **Find work** | **My gigs** |
| [![Find work](docs/screenshots/fundi-find-work.png)](docs/screenshots/fundi-find-work.png) | [![My gigs](docs/screenshots/fundi-my-gigs.png)](docs/screenshots/fundi-my-gigs.png) |
| Open jobs with site ratings, saved jobs, applications and job alerts. | Log → contractor verifies → mark complete. Rate the site afterwards. |
| **Earnings statement** | **Credit score and certificate** |
| [![Statement](docs/screenshots/fundi-statement.png)](docs/screenshots/fundi-statement.png) | [![Credit score](docs/screenshots/fundi-credit-score.png)](docs/screenshots/fundi-credit-score.png) |
| Verified work and agreed pay for any period, as CSV, for a SACCO or lender. | How the score is earned, and a shareable verified-work certificate. |
| **Work profile and your data** | **On a phone** |
| [![Profile](docs/screenshots/fundi-profile.png)](docs/screenshots/fundi-profile.png) | <img src="docs/screenshots/fundi-mobile.png" alt="Fundi Pro on a phone" width="300"> |
| Trades, experience, day rate, availability; download or delete your data. | Installable as an app (PWA). |

### Sign-in

| **Jenga Pro** | **Fundi Pro** |
|---|---|
| [![Jenga Pro sign-in](docs/screenshots/jenga-login.png)](docs/screenshots/jenga-login.png) | [![Fundi Pro sign-in](docs/screenshots/fundi-login.png)](docs/screenshots/fundi-login.png) |

To refresh them, start the dev stack, run
`docker compose exec backend python manage.py seed_demo_data --reset`, then
[`python3 scripts/screenshots.py`](scripts/screenshots.py) (headless Chrome, 1440×900).

Architecture, design decisions and known issues: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Git history and how the repos were merged: [docs/GIT-HISTORY.md](docs/GIT-HISTORY.md).

```
fundi-jenga-pro/
├── backend/                 Django project (project/ = settings, app/ = API)
│   ├── Dockerfile
│   └── docker-entrypoint.sh runs migrations, then gunicorn
├── frontend/
│   ├── fundi-pro/           Angular worker portal   (Dockerfile: dev + runtime targets)
│   └── jenga-pro/           Angular contractor portal
├── docs/
├── scripts/build-pages.sh   static GitHub Pages build of both portals
├── .github/workflows/       GitHub Pages deployment
├── deploy/Caddyfile         TLS reverse proxy config (production override)
├── docker-compose.yml       full stack (production-style, localhost ports)
├── docker-compose.dev.yml   live-reload override
├── docker-compose.prod.yml  HTTPS override: Caddy on 80/443, nothing else published
├── render.yaml              Render Blueprint: the whole platform as Docker services
├── .env.example             every configuration variable, documented
└── .env                     your local copy (gitignored, never commit)
```

## Prerequisites

- Docker Engine 24+ and Docker Compose v2.20+ (`docker compose version`)
- ~4 GB free disk for images
- Optional, for running outside Docker: Python 3.11, Node.js 22 (or 20.19+), PostgreSQL 16

## Quick start (Docker)

```bash
cp .env.example .env          # then edit: SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD,
                              # M-Pesa / SMTP / Africa's Talking credentials
docker compose up -d --build  # first build takes several minutes
docker compose ps             # wait until every service is "healthy"
docker compose exec backend python manage.py createsuperuser
```

| What | URL |
|---|---|
| Fundi Pro (worker portal) | http://localhost:4200 |
| Jenga Pro (contractor portal) | http://localhost:4300 |
| Backend API | http://localhost:8000/api/ |
| Django admin | http://localhost:8000/admin/ |
| Health check | http://localhost:8000/healthz/ |

Ports are set in `.env` (`BACKEND_PORT`, `FUNDI_PRO_PORT`, `JENGA_PRO_PORT`) and bound to
`BIND_ADDRESS` (default `127.0.0.1`, this machine only). Postgres and Redis are not
published at all; they're only reachable on the internal `data` network.

### Test accounts

Seed one ready-to-use account per portal (email already verified):

```bash
docker compose exec backend python manage.py seed_test_users
```

| Portal | URL | Username | Password | Role (`account_type`) |
|---|---|---|---|---|
| Jenga Pro | http://localhost:4300 | `jenga-pro` | `JengaPro2026!` | Contractor / supervisor (`02`) |
| Fundi Pro | http://localhost:4200 | `fundi-pro` | `FundiPro2026!` | Fundi / worker (`01`) |

You can also log in with the email (`jenga-pro@example.com`, `fundi-pro@example.com`).
Each portal only accepts its own role, so use the matching account. Re-running the command
resets the passwords. Run it again after `docker compose down -v`, which wipes the database.

> These credentials are public. The command refuses to run in HTTPS production mode
> (`docker-compose.prod.yml`) unless you pass `--force`. Never seed them on a real deployment.

### Install as an app (PWA)

Both portals are installable progressive web apps. On Android/Chrome use *Install app* (user menu or
browser prompt); on iPhone use *Share → Add to Home Screen*. The service worker caches only the app's
own files (code, styles, icons, fonts), never API data, so shared phones don't keep anyone's
records. It's active in production builds only.

### Demo data (local only)

To see the portals with realistic content (2 sites, 6 fundis, ~15 gigs, ratings, job posts,
M-Pesa payments, a dispute), run:

```bash
docker compose exec backend python manage.py seed_demo_data --reset
```

It builds on the test accounts above. The other fundis' password is `DemoFundi2026!`. It refuses to
run in production mode.

### The two portals

| Jenga Pro (contractors) | Fundi Pro (workers) |
|---|---|
| **Dashboard:** greeting, quick actions, verification queue with one-tap *Verify*, top workers, sites | **Dashboard:** credit score and level, *Mark complete (+5)*, ID prompt, recent work, certificate |
| **Verify gigs:** queue with bulk verify · **All gigs:** tabs, CSV export, star ratings | **My gigs:** Waiting / Ready to complete / Completed, report a problem (dispute) |
| **Workers:** everyone who worked at your sites, plus lookup of any fundi's verified record | **Log a gig:** pick site, then that site's trades · **Find work:** contractors' job posts |
| **Sites**, **Job types**, **Job posts** (advertise open work) | **Credit score:** history, how to earn points, share the work certificate |
| **M-Pesa payments:** STK prompt to your phone, history, CSV | **ID verification** (camera capture) · **Payments received** (M-Pesa proof with OCR) |
| **Job posts:** applicants with their verified record; *Accept* / *Decline* | **Find work:** *I'm interested* on job posts, acceptance alerts with the site's number |
| **On site today:** who checked in at your sites | **I'm on site today:** daily check-in on active verified gigs |
| **Getting started** checklist for new contractors | **Getting started** checklist; printable work certificate (*Print / Save as PDF*) |

Both share one design system (`frontend/design-system/`): a grouped sidebar, a top bar with
**Ctrl K** search, notifications and the user menu, light and dark themes, and a phone layout.
After editing it, run `scripts/sync-design.sh` (CI fails if a portal's copy differs). Icons come from a
subset of Material Symbols. After using a new icon, run `scripts/icons.py`.

### Development mode (live reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- backend runs `manage.py runserver` with `./backend` mounted and `DEBUG=True`
- frontends run `ng serve` with their source mounted. They use
  `src/environments/environment.ts` (API `http://127.0.0.1:8000/`)

## Hosting

| Part | Where | URL |
|---|---|---|
| Fundi Pro, Jenga Pro (static Angular builds) | GitHub Pages | `https://dennis027.github.io/Jenga-and-Fundi-Pro/fundi-pro/`, `/jenga-pro/` |
| API (Django) | Render, Docker, free | `https://fundi-jenga-api.onrender.com` |
| Database | Neon Postgres (us-east-1) | — |

## Deploying the API to Render (Docker)

[render.yaml](render.yaml) is a Render Blueprint for the API, built from the same
Dockerfile as the local stack:

| Render service | Type | Plan | Public URL |
|---|---|---|---|
| `fundi-jenga-api` | Docker web service | free | `https://fundi-jenga-api.onrender.com` |
| `fundi-jenga-redis` | Key Value (Redis) | free, 25 MB, private network only | (internal) |

The **database stays on Neon** (`us-east-1`), so no data moves. All services are in Render's
`virginia` region, next to Neon. Migrations run automatically when the API starts.

1. Push this repo to GitHub (see [docs/GIT-HISTORY.md](docs/GIT-HISTORY.md)).
2. Render dashboard → **New → Blueprint** → select the repo → Render reads `render.yaml`.
3. Render asks for the `sync: false` secrets. Copy them from your local, gitignored
   `.env.render` (or later: service → **Environment → Add from .env** and paste the file).
4. **Apply.** Render builds the images. The API is healthy when `/healthz/` returns
   `{"status": "ok", "checks": {"database": "ok", "redis": "ok"}}`.
5. Verify `https://fundi-jenga-api.onrender.com/healthz/`. The portals are on GitHub Pages
   (next section). To create the test accounts there, run
   `python manage.py seed_test_users --force` against the live database.

Wired automatically: `REDIS_URL` (from the Key Value instance), a new random `SECRET_KEY`,
the `onrender.com` host in `ALLOWED_HOSTS`, `PORT`, HTTPS redirect, secure cookies and HSTS.
The API accepts browser requests from `https://dennis027.github.io` (`CORS_ALLOWED_ORIGINS`,
`CSRF_TRUSTED_ORIGINS`).

**Moving off the old service (`fundi-jenga-oro`):**
- It keeps running until you delete it. Delete it only after the new services work.
- Clients that call `https://fundi-jenga-oro.onrender.com` must change to
  `https://fundi-jenga-api.onrender.com`. That includes the Flutter app. The portals already
  use the new API. A custom domain (e.g. `api.yourdomain.com`)
  on the API service avoids this for future moves.
- Update the M-Pesa callback URL registered with Safaricom, if it is fixed there. The API
  sends `MPESA_CALLBACK_URL` with each STK push, and it's preset to the new host.
- If Render adds a suffix to any service name (name already taken), update `API_URL`,
  `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `MPESA_CALLBACK_URL` in `render.yaml`.

Everything runs on Render's **free** tier. Free web services sleep after ~15 minutes idle;
the first request then takes up to a minute. Free services also have **no persistent disk**,
so uploaded files (profile photos, ID images, payment screenshots) are lost whenever the API
restarts, redeploys or wakes up. Database data on Neon is unaffected. For persistent uploads,
change the API to `plan: 0.5c-512mb` and add the `disk` block shown in `render.yaml`.
The free Key Value instance has no persistence, which is fine here: it only holds cache,
sessions (backed by Postgres) and short-lived OTP codes. A restart just forces new OTPs.

## GitHub Pages (both portals — the only frontend hosting)

`.github/workflows/pages.yml` builds both portals on every push to `main` that touches
`frontend/` and publishes them as **one** Pages site:

| Page | URL |
|---|---|
| Landing page | `https://<owner>.github.io/<repo>/` |
| Fundi Pro | `https://<owner>.github.io/<repo>/fundi-pro/` |
| Jenga Pro | `https://<owner>.github.io/<repo>/jenga-pro/` |

- **One-time setup:** repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
- Pages only hosts the static frontends. They call the API in
  `src/environments/environment.prod.ts` (the Render backend). To use another API, set the
  repository variable `PAGES_API_URL` (Settings → Secrets and variables → Actions → Variables).
- The API must allow the Pages origin. When the backend runs this repo's code, include
  `https://<owner>.github.io` in `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.
- Custom domain: set the variable `PAGES_BASE_PATH=/`.
- Build the same site locally:
  `BASE_PATH=/<repo> scripts/build-pages.sh` (output in `_site/`).

## Configuration

All configuration lives in the root `.env` (template: [.env.example](.env.example)).
Compose uses it for variable substitution and passes it to the backend container.
The backend's `DB_*` and `REDIS_URL` values are derived inside
`docker-compose.yml` from `POSTGRES_*` / `REDIS_PASSWORD`, so each secret is defined once.
Services address each other by Docker service name (`db`, `redis`, `backend`).

**Frontend API URL.** Both Angular apps prerender every route at build time and call the
API from the browser, so the API URL is baked into the bundle. Set `PUBLIC_API_URL` (the URL
as the *browser* sees it, ending in `/`) and rebuild:
`docker compose build fundi-pro jenga-pro`. Without Docker, `ng build` uses
`src/environments/environment.prod.ts` (the Render URL).

## Production (HTTPS)

`docker-compose.prod.yml` adds **Caddy** as the only public entry point. Caddy gets and
renews Let's Encrypt certificates automatically and proxies three hostnames:

| Hostname (`.env`) | Proxied to |
|---|---|
| `API_DOMAIN` | `backend:8000` |
| `FUNDI_DOMAIN` | `fundi-pro:4000` |
| `JENGA_DOMAIN` | `jenga-pro:4000` |

1. Point the three DNS names at the server and open ports 80 and 443.
2. In `.env`, set `API_DOMAIN`, `FUNDI_DOMAIN`, `JENGA_DOMAIN`, `ACME_EMAIL`, a long random
   `SECRET_KEY`, and strong `POSTGRES_PASSWORD` / `REDIS_PASSWORD`.
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

In this mode the backend and frontends publish no ports. `ALLOWED_HOSTS`, CORS/CSRF origins,
the frontends' API URL (`https://API_DOMAIN/`), the HTTP→HTTPS redirect, secure cookies,
HSTS and `X-Forwarded-*` handling are all derived from the domains, so you don't set them by
hand. `manage.py check --deploy` reports only the opt-in `SECURE_HSTS_PRELOAD`. Raise
`SECURE_HSTS_SECONDS` to `31536000` once HTTPS is stable.

Local test of the production setup, using Caddy's internal CA and `*.localhost` names:

```bash
API_DOMAIN=api.localhost FUNDI_DOMAIN=fundi.localhost JENGA_DOMAIN=jenga.localhost \
ACME_EMAIL=ops@example.com CADDY_GLOBAL_OPTIONS=local_certs PUBLIC_BIND_ADDRESS=127.0.0.1 \
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
curl -k https://api.localhost/healthz/
```

The default and prod modes bake different API URLs into the same frontend image tags, so
always pass `--build` when switching between them.

## Redis

The `redis` service (Redis 7, password protected, AOF persistence in the `redis-data` volume,
`REDIS_MAXMEMORY` with LRU eviction) is used by the backend as:

- **Django cache** (`django.core.cache.backends.redis.RedisCache`, key prefix `fjp`)
- **M-Pesa OAuth token cache.** The Daraja token (valid ~1 h) is reused instead of
  being requested on every STK push. If Redis is down, the backend falls back to a direct request.
- **Session cache** (`cached_db` engine: Redis for reads, Postgres stays the source of truth)

It is enabled when `REDIS_URL` is set (Compose does this). Without it, Django falls back to
in-process memory caching, so a plain local `runserver` still works.

```bash
docker compose exec redis redis-cli ping                 # PONG (auth via REDISCLI_AUTH)
docker compose exec redis redis-cli --scan --pattern 'fjp:*'
curl -s localhost:8000/healthz/                          # {"status":"ok","checks":{"database":"ok","redis":"ok"}}
```

## Phone OTP API

`POST /send-otp/` `{"phone": "+2547..."}` sends a 6-digit code by SMS (Africa's Talking).
The code is stored **only server-side**: hashed, in Redis, for `OTP_TTL_SECONDS` (5 min).
`POST /verify-otp/` `{"phone": "...", "otp": "123456"}` returns `{"verified": true}` (200),
or 400 for an invalid or expired code and 429 after `OTP_MAX_VERIFY_ATTEMPTS` (5) wrong tries.
Codes are single-use. Sending is rate-limited to one per `OTP_RESEND_COOLDOWN_SECONDS` (60 s),
`OTP_MAX_SENDS_PER_HOUR` (5) per phone and `OTP_MAX_SENDS_PER_IP_PER_HOUR` (20) per client IP.
These return 429 with `Retry-After`.

On success `/verify-otp/` also returns a `phone_token` (valid `OTP_PHONE_TOKEN_MAX_AGE`, 15 min).
With `REQUIRE_PHONE_OTP=True`, registering with a phone number or changing it in the profile
requires that token (`phone_token` field). It's off by default because neither web portal has an
OTP step yet.

> **Client migration:** `/send-otp/` no longer returns the code. Clients that compared it
> locally (most likely the Flutter mobile app; neither web portal uses OTP) must call
> `/verify-otp/`. During the transition you can set `OTP_RETURN_CODE_IN_RESPONSE=True`.
> That is insecure, so turn it off again once the app is updated.

## Platform features

| Feature | Endpoint(s) | Who |
|---|---|---|
| **Hiring** | `POST /api/gigs-available/<id>/apply/`, `GET /api/my-applications/`, `GET /api/gigs-available/<id>/applications/`, `POST /api/applications/<id>/decide/` | Fundi applies; post's contractor decides |
| **Site check-in** | `POST /api/gigs/<id>/check-in/` (once a day, verified gigs), `GET /api/my-check-ins/today/`, `GET /api/contractor/on-site-today/` | Fundi checks in; contractor sees who is on site |
| **Work certificate** | `GET /api/certificate/link/` returns a signed link; `GET /certificate/<token>/` is the public page with a QR code; `GET /api/certificate/<token>/` is the JSON version | Fundi creates; anyone with the link views |
| **Gig ratings** (1–5 stars) | `POST /api/gig-history/<id>/rate/` | Contractor who owns the site |
| **Disputes** | `GET/POST /api/disputes/`, `POST /api/disputes/<id>/resolve/` | Worker / site contractor raise; staff resolve |
| **USSD menu** (score, recent gigs, ID status) | `POST /ussd/?token=…` (Africa's Talking callback) | Fundis without smartphones |
| **Notifications inbox** | `GET /api/notifications/`, `POST /api/notifications/read/` | Everyone (the bell's “Recent” list) |
| **Work profile & availability** | `GET/PATCH /api/me/work-profile/` | Fundi (trades, years, day rate, bio, available / busy until) |
| **Find workers by trade** | `GET /api/workers/available/?trade=&county=&available=1` | Contractor |
| **Job alerts** | `GET/POST /api/job-alerts/`, `DELETE /api/job-alerts/<id>/` | Fundi (in-app, optional SMS) |
| **Saved jobs** | `POST /api/gigs-available/<id>/save/` (toggle), `GET /api/saved-posts/` | Fundi |
| **Withdraw an application** | `POST /api/applications/<id>/withdraw/` | Fundi (pending only) |
| **Invite a worker** | `POST /api/gigs-available/<id>/invite/`, `POST /api/applications/<id>/respond/` | Contractor invites; fundi accepts or declines |
| **Places & auto-close** | `positions` on job posts; `POST /api/gigs-available/<id>/toggle/` | Post closes when enough workers are accepted |
| **Reject a gig with a reason** | `POST /api/gigs/<id>/reject/` | Site's contractor (unverified gigs only) |
| **Bulk verify** | `POST /api/gigs/verify-bulk/` (up to 100 ids) | Site's contractor |
| **My crew** | `GET/POST /api/crew/`, `DELETE /api/crew/<username>/` | Contractor |
| **Workers rate sites** | `POST /api/gig-history/<id>/rate-site/`, `GET /api/fundi/completed/`, `GET /api/contractor/site-ratings/` | Fundi rates (stars, paid on time); shown on job posts |
| **Safety incidents** | `GET/POST /api/incidents/`, `POST /api/incidents/<id>/resolve/` | Anyone working at the site reports; site's contractor resolves |
| **Attendance register** | `GET /api/contractor/attendance/?from=&to=&org=[&csv=1]` | Contractor |
| **Payroll** | `GET /api/contractor/payroll/?from=&to=&org=[&csv=1]` | Contractor (agreed pay, gig days, days checked in) |
| **Site labour budgets** | `GET/POST /api/contractor/budgets/` | Contractor |
| **Activity log** | `GET /api/activity/?org=` | Contractor |
| **Earnings statement** | `GET /api/fundi/statement/?from=&to=[&csv=1]` | Fundi (for SACCOs, lenders, landlords) |
| **Your data** | `GET /api/account/export/` (JSON), `POST /api/account/delete/` (password) | Everyone (Data Protection Act) |
| **API reference** | `/api/docs/` (Swagger UI), `/api/schema/` (OpenAPI) | Developers, Flutter app |

The certificate shows only platform-verified facts (contractor-verified gigs, days worked,
trades, sites, ratings, credit score, identity status). It never shows phone numbers, national
IDs or client details. Links expire after `CERTIFICATE_MAX_AGE_DAYS` (90). In Fundi Pro, the
**Share my certificate** button is on the credit score page.

Where they are in the portals: **Fundi Pro** — Find work (saved jobs, applications, invitations,
job alerts), My gigs (rate site, *Statement*), Site safety, My profile (work profile, your data).
**Jenga Pro** — Verify gigs (bulk verify, reject), Workers (my crew, find by trade, invite), Job
posts (places, close/reopen, invite crew), Payroll & attendance (payroll, attendance, budgets, site
ratings), Site safety, Activity, My profile (your data).

Deleting an account erases the person's name, phone, ID number, photo and work profile and
signs them out everywhere. Verified work stays on contractors' records as “Deleted user” so
their payroll and history still add up.

### Trust rules (enforced by the API, covered by tests)

- **Credit score:** changes only through gig verification (+5), gig completion (+5) and
  identity approval (+20, once). It's clamped to 0–100 and every change is in the score
  history. Users can't edit it.
- **Gigs:** only the contractor who owns the gig's site can verify it. Completion is allowed
  for the gig's worker or that contractor.
- **Identity:** only staff approve or reject IDs, in Django admin or via the API. ID photos
  are private: staff see them in admin, and the API returns short-lived signed links.
- **Data access:** users see their own gigs, sites and payments. In search, other people's
  gigs hide the client phone number and amount. Platform reports and the user list are
  staff-only.
- **M-Pesa callbacks:** must carry `MPESA_CALLBACK_TOKEN`, match a payment the app started,
  and match its amount. Each is recorded once.
- **Score audit:** `python manage.py audit_credit_scores [--fix]` lists scores that don't
  match their history.

### Language

Fundi Pro can be used in **Kiswahili**: open the user menu (top right) and choose *Kiswahili*.
The choice is remembered on that device. Strings are in
`frontend/fundi-pro/src/app/shell/i18n-dict.ts`; text without an entry stays in English.

### Staff back office

Create a staff account: `docker compose exec backend python manage.py createsuperuser`.
On Render free there's no shell, so run it from your machine against the production
`DATABASE_URL`. Then open `/admin/`:
- **Verification requests:** ID and selfie previews, with approve/reject actions.
- **Gig disputes:** set the status to resolved or rejected.
- **Credit score history and M-Pesa transactions:** read-only.

### Optional integrations

| Integration | Enable with | Notes |
|---|---|---|
| Object storage for uploads | `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Needed on Render free (no disk). Cloudflare R2 has a free 10 GB tier. The bucket stays private, with signed URLs. |
| Error monitoring | `SENTRY_DSN` | Sentry free tier; no personal data sent. |
| USSD | `USSD_CALLBACK_TOKEN` | Set the Africa's Talking USSD callback to `https://<api>/ussd/?token=<value>`. |
| SMS alerts | `SMS_NOTIFICATIONS=True` | Sends an SMS via Africa's Talking when a gig is verified, an application is accepted, or an ID is approved or rejected. Each SMS costs money. Off by default. |
| Live M-Pesa | `MPESA_BASE_URL=https://api.safaricom.co.ke` + production `MPESA_*` credentials | Go live on the Daraja portal first. Set `MPESA_CALLBACK_TOKEN` and `MPESA_ACCOUNT_REFERENCE`. |

## Tests & CI

```bash
docker compose run --rm --no-deps -v ./backend:/app -e RUN_MIGRATIONS=0 backend python manage.py test app
```

90 tests cover the trust rules above, plus:
- OTP and phone tokens, and M-Pesa callbacks and the token cache;
- private media and the source-file exposure regression;
- the certificate, ratings, disputes, USSD and admin review;
- the workforce features: inbox, alerts, invitations, crew, site ratings, incidents,
  reject / bulk verify, attendance, payroll, budgets, statements, data export and account deletion;
- health checks and the API docs.

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and pull request:
- a missing-migrations check, Django checks, and the tests on Postgres 16;
- builds of both portals and the backend image.

On `main`, it then deploys all three Render services **if** the repository secret
`RENDER_API_KEY` is set.

## Database & migrations

PostgreSQL 16 runs in the `db` service with data in the `postgres-data` volume.
**Migrations run automatically** when the backend container starts (`RUN_MIGRATIONS=0` to
disable). Manually:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py showmigrations
docker compose exec backend python manage.py makemigrations   # dev mode (source mounted)
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Import an existing database (e.g. your previous local Postgres):

```bash
pg_dump -Fc -h localhost -U <old_user> <old_db> > dump.pgdump
docker compose exec -T db pg_restore -U fundi_jenga -d fundi_jenga --clean --if-exists --no-owner < dump.pgdump
```

Copy existing uploads into the media volume:

```bash
tar -C backend -c MEDIA | docker compose exec -T backend tar -C /data/media -x   # keeps files owned by the app user
```

Backup:

```bash
docker compose exec -T db pg_dump -U fundi_jenga -Fc fundi_jenga > backup-$(date +%F).pgdump
```

## Operations

```bash
docker compose ps                            # status + health
docker compose logs -f                       # all logs
docker compose logs -f backend               # one service
docker compose restart backend
docker compose up -d --build backend         # rebuild after code changes
docker compose down                          # stop (data volumes kept)
docker compose down -v                       # stop AND delete db / redis / media data
```

All services use `restart: unless-stopped`. Start order is enforced with health checks:
`db` + `redis` → `backend` → `fundi-pro` + `jenga-pro`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `POSTGRES_PASSWORD must be set` | Create `.env` from `.env.example`. |
| Backend `unhealthy` | `docker compose logs backend`; `curl localhost:8000/healthz/` shows which check fails. |
| `SECRET_KEY must be set when DEBUG is False` | Set `SECRET_KEY` in `.env`. |
| Browser: CORS error | Add the exact frontend origin (scheme + host + port) to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`, then `docker compose up -d backend`. |
| Frontend calls the wrong API | `PUBLIC_API_URL` is build-time: `docker compose build fundi-pro jenga-pro && docker compose up -d`. |
| `DisallowedHost` / HTTP 400 | Add the host name to `ALLOWED_HOSTS`. |
| Changed `POSTGRES_PASSWORD`, DB auth fails | Postgres keeps the password from first init. Change it with `ALTER USER`, or `docker compose down -v` (destroys data). |
| Redis `NOAUTH` | `REDIS_PASSWORD` must be URL-safe; recreate with `docker compose up -d --force-recreate redis backend`. |
| Port already in use | Change `*_PORT` in `.env`. |
| Host `npm ci` fails with EACCES in `node_modules` after using dev mode | Docker created the dev-mode mount point as root: `sudo rm -rf frontend/*/node_modules frontend/*/.angular`, then recreate them as your user (`mkdir`) before the next dev run. |
| Uploaded image 404 | Check `SERVE_MEDIA=True` and that files are under `/data/media/MEDIA/` in the backend container. |

## Running without Docker

```bash
# backend (needs a local Postgres; put DEBUG=True and DB_* in backend/.env)
cd backend && python3.11 -m venv venv && . venv/bin/activate
pip install -r requirements.txt && python manage.py migrate && python manage.py runserver

# frontends
cd frontend/fundi-pro && npm ci && npm start                                       # :4200
cd frontend/jenga-pro && npm ci && npx ng serve --port 4300                         # :4300
```
# Jenga-and-Fundi-Pro
# Jenga-and-Fundi-Pro
