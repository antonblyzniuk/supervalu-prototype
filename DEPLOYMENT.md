# Deploying to Railway

Three Railway services in one project: **Postgres**, **backend**, **frontend**.
Both apps ship a Dockerfile, so Railway builds them directly — no Nixpacks
guessing, and what runs in production is what you can run locally.

The frontend proxies `/api`, `/admin`, `/media` and `/static` to the backend, so
the deployed app is **same-origin**: no CORS, and the relative media URLs the
API returns for signatures and photos resolve correctly.

```
browser → frontend (nginx + SPA) ──proxy──> backend (gunicorn) → Postgres
                                                    └─ volume: /data/media
```

> ### Set **Root Directory** on both services — do this first
>
> | Service | Root Directory |
> | --- | --- |
> | backend | `backend` |
> | frontend | `frontend` |
>
> Railway → service → **Settings → Source → Root Directory**.
>
> This is what sets the Docker **build context**. Each Dockerfile copies files
> relative to its own folder (`COPY nginx.conf.template`, `COPY package.json`),
> so with the repo root as context those paths do not exist and the build dies
> with `"/nginx.conf.template": not found`.
>
> Do **not** instead set "Dockerfile Path" to `frontend/Dockerfile` and leave
> Root Directory empty — that points Railway at the right Dockerfile but keeps
> the wrong context, which is exactly the failure above. Setting Root Directory
> also makes Railway pick up that folder's `railway.json`.

---

## 1. Postgres

Add the Postgres database from Railway's catalogue. It exposes `DATABASE_URL`,
which is the only database variable the backend needs.

## 2. Backend service

Create a service from this repo and set **Root Directory** to `backend` (see the
note above — the build fails without it). Railway then picks up
`backend/railway.json`: Dockerfile builder, health check on `/api/health/`.

Variables:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `DJANGO_SECRET_KEY` | a fresh 64-char random string — see below |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` (the Railway domain is added automatically) |
| `CSRF_TRUSTED_ORIGINS` | `https://<your-frontend-domain>` |
| `CORS_ALLOWED_ORIGINS` | `https://<your-frontend-domain>` |
| `DJANGO_MEDIA_ROOT` | `/data/media` (must match the volume mount, below) |
| `DJANGO_TIME_ZONE` | `Europe/Dublin` |
| `WEB_CONCURRENCY` | `3` |

Generate the secret key with an **alphanumeric-only** value — Railway and Docker
Compose both interpolate `$` in variable values, which silently corrupts a key
containing one:

```bash
python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(64)))"
```

`PORT` is injected by Railway and gunicorn binds to it; don't set it yourself.

### Volume for uploads (required)

Docket photos and signatures are files on disk. **Railway containers are wiped
on every redeploy**, so without a volume every image uploaded since the last
deploy disappears.

Add a Volume to the backend service, mount path `/data`, and keep
`DJANGO_MEDIA_ROOT=/data/media`. The entrypoint creates the directory on boot.

> At real scale, move uploads to object storage (S3 / Cloudflare R2) instead —
> gunicorn serving image files ties up a worker per request. Fine for three
> stores; not fine for thirty.

### Migrations

The entrypoint runs `migrate` on every boot (`RUN_MIGRATIONS=1` is the default),
so a deploy applies migrations automatically. Set `RUN_MIGRATIONS=0` if you'd
rather run them by hand from `railway run`.

Static files are collected at image build time, so no `collectstatic` step is
needed at boot.

## 3. Frontend service

Create a second service from the same repo with **Root Directory** set to
`frontend` — again, the build fails without it.

| Variable | Value |
| --- | --- |
| `BACKEND_ORIGIN` | `https://<your-backend-domain>` — no trailing slash |
| `VITE_API_BASE_URL` | leave unset (defaults to `/api`, which the proxy handles) |

`PORT` is injected by Railway; nginx renders it into its config at start-up.

`BACKEND_ORIGIN` is read at container start, so changing it only needs a
restart. `VITE_API_BASE_URL` is inlined by Vite at **build** time — changing it
requires a rebuild, which is exactly why the default keeps everything relative.

## 4. First run

Generate the domains for both services, then create the first admin:

```bash
railway run --service backend python manage.py createsuperuser
```

Sign in at `https://<frontend-domain>/`, open **Team**, and add colleagues with
their store assignments. A staff account with no store assigned can see nothing
until a manager assigns one.

---

## Deploy order

1. Postgres
2. Backend — deploy, confirm `https://<backend>/api/health/` returns
   `{"status":"ok","database":"ok"}`
3. Frontend — set `BACKEND_ORIGIN` to the backend domain, deploy
4. Set the backend's `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` to the
   frontend domain and redeploy the backend

The order is a convenience, not a requirement — the frontend deploys and passes
its health check whether or not the backend exists yet.

## Verifying a deploy

```bash
curl https://<frontend-domain>/api/health/     # proxy + database
curl -I https://<frontend-domain>/             # SPA shell
curl -I https://<frontend-domain>/dockets      # SPA routing fallback
```

Then sign in and check that a docket's signature image renders — that exercises
the media volume, the proxy and the relative-URL handling in one go.

## Troubleshooting

**Build fails with `"/nginx.conf.template": not found`** (or
`"/package-lock.json"`, or `"/requirements.txt"`) — the build context is the
repo root instead of the service folder. Set **Root Directory** to `frontend`
(or `backend`) as described at the top, and clear any "Dockerfile Path"
override so it stays the default `Dockerfile`.

Reproduce and confirm the same thing locally:

```bash
docker build -f frontend/Dockerfile --target prod .          # fails, wrong context
docker build -f frontend/Dockerfile --target prod ./frontend  # succeeds
```


**Frontend healthcheck fails, logs show `host not found in upstream`** — this
should no longer happen: the upstream is resolved at request time, so nginx
starts even when `BACKEND_ORIGIN` points at something that does not exist yet.
If you see it, the image predates that fix — redeploy from `main`.

The frontend can be deployed before the backend exists. It serves the SPA
normally and returns 502 on `/api` until `BACKEND_ORIGIN` points somewhere real.

**Frontend is up but every API call returns 502** — `BACKEND_ORIGIN` is unset,
wrong, or has a trailing slash. It must be the backend's full origin with no
path: `https://backend-production-1234.up.railway.app`.

**Redirect loop / `ERR_TOO_MANY_REDIRECTS`** — Django's `SECURE_SSL_REDIRECT` is
on whenever `DJANGO_DEBUG=False`. nginx forwards the edge's `X-Forwarded-Proto`,
so this should work; if a proxy in front strips that header, set
`SECURE_SSL_REDIRECT=False` on the backend.

**`DisallowedHost`** — the Railway domain is trusted automatically via
`RAILWAY_PUBLIC_DOMAIN`. A custom domain must be added to
`DJANGO_ALLOWED_HOSTS` by hand.

**Signatures/photos 404** — the volume is missing or `DJANGO_MEDIA_ROOT` does
not match its mount path.

**Images vanish after a deploy** — no volume mounted; see above.

**CSRF failures in `/admin/`** — add the *frontend* origin to
`CSRF_TRUSTED_ORIGINS`; that is the origin the browser posts from.

---

## Running the production images locally

Worth doing before any deploy — it catches the same problems without a push:

```bash
BACKEND_TARGET=prod FRONTEND_TARGET=prod DJANGO_DEBUG=False \
SECURE_SSL_REDIRECT=False FRONTEND_PORT=8088 \
docker compose up --build

curl http://localhost:8088/api/health/
```

`SECURE_SSL_REDIRECT=False` is only needed because the local test runs over
plain http.
