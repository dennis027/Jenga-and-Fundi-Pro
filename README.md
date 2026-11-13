# Fundi / Jenga Pro

Monorepo for the Fundi / Jenga Pro platform: construction workers (*fundis*)
log gigs, and contractors verify them, manage sites and workers, and pay via
M-Pesa.

| Component | Path | Stack | Purpose |
|---|---|---|---|
| **Backend API** | [backend/](backend/) | Django 4.2, DRF, SimpleJWT, PostgreSQL, Redis | REST API, auth, M-Pesa STK push, SMS OTP, OCR, reports |
| **Fundi Pro** | [frontend/fundi-pro/](frontend/fundi-pro/) | Angular 20 (SSR / prerender), Material 20 | Worker portal: log gigs, work history, credit score, payments |
| **Jenga Pro** | [frontend/jenga-pro/](frontend/jenga-pro/) | Angular 20 (SSR / prerender), Material 21 | Contractor portal: verify gigs, manage workers/sites, reports, M-Pesa |

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
├── docker-compose.yml       full stack (production-style)
├── docker-compose.dev.yml   live-reload override
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

### Development mode (live reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- backend runs `manage.py runserver` with `./backend` mounted and `DEBUG=True`
- frontends run `ng serve` with their source mounted. They use
  `src/environments/environment.ts` (API `http://127.0.0.1:8000/`)

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

**Production checklist:** `DEBUG=False`, a long random `SECRET_KEY`, strong DB and Redis
passwords, `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` set to your real
domains, `PUBLIC_API_URL` set to the public API URL, and a TLS reverse proxy (nginx, Caddy,
Traefik) in front of ports 8000/4200/4300.

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
cd frontend/jenga-pro && npm ci --legacy-peer-deps && npx ng serve --port 4300     # :4300
```
