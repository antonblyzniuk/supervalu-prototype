# supervalu-prototype

Internal tooling for SuperValu store staff and management. React SPA on top of a
Django REST Framework API, PostgreSQL for storage, everything running under
Docker Compose.

## Stack

| Layer    | Choice                                                            |
| -------- | ----------------------------------------------------------------- |
| Frontend | React 19 + TypeScript + Vite, React Router, TanStack Query, axios  |
| Backend  | Django 5.2 + Django REST Framework, SimpleJWT, drf-spectacular     |
| Database | PostgreSQL 17                                                     |
| Runtime  | Docker Compose (`db`, `backend`, `frontend`)                       |

## Layout

```
.
├── docker-compose.yml
├── .env.example            # copy to .env
├── backend/
│   ├── config/             # settings, root urls, wsgi/asgi
│   ├── apps/
│   │   ├── accounts/       # custom User (email login, roles), JWT endpoints
│   │   ├── core/           # shared base models, pagination, permissions, health
│   │   ├── stores/         # the three branches (seeded by migration)
│   │   └── dockets/        # docket registers, summaries, PDF/JSON export
│   ├── Dockerfile          # targets: dev | prod
│   └── entrypoint.sh       # waits for Postgres, migrates, then runs CMD
└── frontend/
    ├── src/
    │   ├── components/ui/  # Button, Card, Field, Tabs, Modal, Toast…
    │   ├── features/auth/  # auth context, login page, auth API calls
    │   ├── features/dockets/  # the docket feature (forms, list, top sheet)
    │   ├── styles/         # tokens.css, base.css, components.css
    │   ├── lib/            # axios client (JWT + refresh), token storage
    │   ├── pages/          # dashboard, not-found
    │   └── router.tsx
    ├── Dockerfile          # targets: dev | build | prod (nginx)
    └── nginx.conf
```

## The docket system

Replaces the paper registers. Four types, all filed against one of the three
stores:

| Register     | Shape           | Columns / fields                                                       |
| ------------ | --------------- | ---------------------------------------------------------------------- |
| **Ambient**  | Weekly register | Groc, Cigs, Wine, Beers, Spirits, Non Food, News, Promo, Expense        |
| **Chilled**  | Weekly register | Beef, Lamb, Pork, Poultry, Produce, Frozen, Provisions, Deli, Bakery    |
| **Returns**  | Item list       | Supplier, reason, qty/description/cost/retail/total                     |
| **Transfer** | Item list       | From store → to store, department, qty/description/cost/retail/total    |

Every docket carries signatures (drawn on screen with a finger, stylus or
mouse) and photos of the paper docket. Row and column totals compute live as
you type; the header total is always recalculated server-side from the saved
rows, so a client can't post a total that doesn't match its lines.

### Screens

| Route                 | What                                                                      |
| --------------------- | ------------------------------------------------------------------------- |
| `/`                   | Home — greeting and the list of things you can do                         |
| `/dockets`            | All dockets, filterable by store / type / date range / free text          |
| `/dockets/new`        | The four forms (`?type=ambient\|chilled\|returns\|transfer`)               |
| `/dockets/:id`        | Full docket with signatures, photos and per-column totals                 |
| `/dockets/top-sheet`  | Weekly top sheet — one store or the whole group, Sunday→Saturday          |
| `/team`               | Manager-only: assign colleagues to stores, roles, onboarding              |

Dockets is a self-contained section with its own sub-navigation (all / new /
top sheet); Home is purely a launchpad.

### Reporting and export

`/api/dockets/summary/` groups totals by type and by store; `/api/dockets/export/`
downloads the same scope as **JSON** or **PDF**. Both honour the identical
filters, so what you see on screen is what you download:

```
# Whole group, current trading week, as PDF
/api/dockets/export/?output=pdf&week_of=2026-08-05

# One store, ambient only, a date range, as JSON
/api/dockets/export/?output=json&store=skerries&docket_type=ambient&date_from=2026-08-01&date_to=2026-08-31
```

PDFs are rendered server-side with ReportLab — landscape A4, brand header, a
summary page then one block per docket with its signatures and photos embedded.
Rendering on the server (not with jsPDF in the browser) means a manager
exporting from an iPad gets byte-identical output to the office.

The export param is `output`, not `format`: DRF reserves `format` for content
negotiation and would 404 on `format=pdf`.

## Getting started

```bash
cp .env.example .env
docker compose up --build
```

| URL                               | What                            |
| --------------------------------- | ------------------------------- |
| http://localhost:5173             | Frontend (Vite dev server, HMR) |
| http://localhost:8000/api/health/ | API health check                |
| http://localhost:8000/api/docs/   | Swagger UI                      |
| http://localhost:8000/api/redoc/  | ReDoc                           |
| http://localhost:8000/admin/      | Django admin                    |
| localhost:5433                    | Postgres (host-side port)       |

The Vite dev server proxies `/api`, `/admin` and `/static` to the backend
container, so the browser only ever talks to port 5173 and there are no CORS
surprises in development.

Create the first account:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Common commands

```bash
docker compose up -d                 # start
docker compose logs -f backend       # tail logs
docker compose down                  # stop (keeps data)
docker compose down -v               # stop and wipe the database

# Backend
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py shell
docker compose exec backend pytest
docker compose exec backend ruff check . --fix

# Frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose exec frontend npm install <pkg>   # then rebuild the image
```

## Auth

Email + password, JWT via SimpleJWT.

| Endpoint                        | Purpose                          |
| ------------------------------- | -------------------------------- |
| `POST /api/auth/token/`         | `{email, password}` → token pair |
| `POST /api/auth/token/refresh/` | rotate the access token          |
| `GET  /api/auth/me/`            | current user profile             |

The frontend keeps tokens in `localStorage` and refreshes them automatically
from a single shared in-flight request (`src/lib/apiClient.ts`). Users carry a
`role` of `staff`, `manager` or `admin`; `apps/core/permissions.py` has
`IsManager` / `IsManagerOrReadOnly` for endpoints that need it. Deleting a
docket is manager-only; everyone signed in can read and file them.

### Roles and store scoping

| Role        | Sees                                                  | Can                                              |
| ----------- | ----------------------------------------------------- | ------------------------------------------------ |
| **staff**   | Only their assigned store, plus transfers arriving there | File and edit dockets for that store           |
| **manager** | All three stores                                      | Everything staff can, plus delete, plus `/team`  |
| **admin**   | All three stores                                      | Everything, plus grant the admin role            |

Store assignment is what grants a staff account access — a staff user with no
store sees nothing and cannot file. Managers set this on `/team`, either inline
in the table or in the edit dialog.

Scoping is enforced server-side in `scoped_dockets()` and in
`DocketSerializer.validate`, so it holds for the list, the detail view, the
summary and both exports. A hand-crafted `?store=` cannot widen it, and a staff
member cannot file a docket against another branch. The UI mirrors the same
rules (locked store pickers, hidden group option) but is not what enforces them.

Sign-in is case-insensitive and addresses are stored lower-cased, so `Aaron@…`
and `aaron@…` are the same account.

## Design system

All styling comes from `src/styles/tokens.css` — brand colour, type scale,
spacing, radii, shadows. `components.css` builds the shared classes (`.card`,
`.btn`, `.input`, `.table`, `.badge`…) on top of those tokens; no component
hardcodes a hex value. New screens compose the primitives in
`src/components/ui/` so everything stays visually consistent.

Responsive and cross-browser notes baked in:

- Wide tables scroll inside `.table-scroll`; the page body never scrolls sideways.
- Inputs are 16px on touch, which stops iOS Safari zooming on focus.
- Signature capture uses Pointer Events, so touch, stylus and mouse share one
  code path in Safari, Chrome and Firefox, and redraws at `devicePixelRatio`.
- Photos are downscaled in a canvas before upload — a 8 MB phone photo becomes
  a ~200 KB JPEG.
- `prefers-reduced-motion` disables transitions; a print stylesheet drops the
  chrome so any screen prints cleanly.

## Adding a feature

1. `docker compose exec backend python manage.py startapp <name> apps/<name>`
   then set `name = "apps.<name>"` in its `apps.py` and add it to `LOCAL_APPS`.
2. Models inherit `TimeStampedModel` (or `UUIDTimeStampedModel`) from
   `apps.core.models`.
3. Serializers + a `ModelViewSet`, routed under `/api/<name>/`.
4. On the frontend, add `src/features/<name>/` with its API calls and screens,
   then register a route in `src/router.tsx`.

## Production build

Both images have a `prod` target — gunicorn for the backend, nginx serving the
static bundle and proxying the API for the frontend:

```bash
BACKEND_TARGET=prod FRONTEND_TARGET=prod DJANGO_DEBUG=False \
SECURE_SSL_REDIRECT=False FRONTEND_PORT=8088 docker compose up --build
```

Set a real `DJANGO_SECRET_KEY`, a real database password and the right
`DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` before running that anywhere
public. `DJANGO_DEBUG=False` turns on HSTS, secure cookies and SSL redirect.

## Deployment

**[DEPLOYMENT.md](DEPLOYMENT.md)** covers Railway end to end — services,
variables, and the volume the uploads directory needs.

## Notes

The existing production site lives in a separate repo
(`aarondoyle2026.github.io`) and is not tracked here.
