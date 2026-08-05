# CLAUDE.md

Internal SuperValu staff/management tooling. React SPA + Django REST Framework +
PostgreSQL, all under Docker Compose. Future work includes parsers and
third-party API integrations.

## Everything runs in Docker

Never run `python manage.py`, `pytest`, `npm` or `psql` on the host — the host
has no virtualenv and Postgres 5432 is occupied by an unrelated container. Use:

```bash
docker compose exec backend <cmd>     # python manage.py ..., pytest, ruff
docker compose exec frontend <cmd>    # npm run lint, npm run build
docker compose up -d / logs -f / down
```

`docker compose run --rm backend ...` works for one-offs when the stack is down.

## Backend conventions

- Apps live under `backend/apps/<name>/` and are listed in `LOCAL_APPS` in
  `config/settings.py` as `apps.<name>`. Each `AppConfig` sets both
  `name = "apps.<name>"` and a short `label`.
- `config/settings.py` is single-file and env-driven via `django-environ`. Add
  new knobs there with a sensible default and document them in `.env.example`.
- Models inherit `TimeStampedModel` / `UUIDTimeStampedModel` from
  `apps.core.models`. Use the UUID variant for anything whose id is exposed
  outside the app.
- `AUTH_USER_MODEL = "accounts.User"` — email is the login field, there is no
  `username`. Reference users with `settings.AUTH_USER_MODEL`, never
  `auth.User`.
- DRF defaults: JWT auth, `IsAuthenticated`, page size 25 via
  `apps.core.pagination.DefaultPagination`. Endpoints that should be public need
  an explicit `permission_classes = (AllowAny,)`.
- Role gating uses `apps.core.permissions.IsManager` / `IsManagerOrReadOnly`,
  backed by `User.role` (`staff` / `manager` / `admin`) and `User.is_manager`.
- Tests are pytest + `pytest-django` under `apps/<name>/tests/`. Lint with
  `ruff` (config in `backend/pyproject.toml`, line length 100).
- New models need a migration committed alongside them:
  `docker compose exec backend python manage.py makemigrations <app>`.

## Roles and store scoping

- `staff` see only their assigned store plus transfers arriving there;
  `manager`/`admin` see the whole group. Enforced in
  `apps/dockets/views.scoped_dockets()` (reads) and
  `DocketSerializer.validate` (writes) — every list, detail, summary and export
  route goes through them. Never bypass those by querying `Docket.objects`
  directly in a view.
- A staff user with `store=None` sees nothing and cannot file. That is
  deliberate; the fix is a manager assigning them a store on `/team`.
- Frontend locks (disabled store pickers, hidden "All stores", hidden Team nav)
  are UX only. The API is the boundary; add both when adding a scoped screen.
- Only an admin can grant or revoke the admin role, and nobody can change their
  own role or deactivate themselves (`TeamMemberSerializer`).
- Emails are stored lower-cased and sign-in is case-insensitive
  (`apps/accounts/auth_serializers.py`). Keep new user-creation paths going
  through `UserManager.create_user` so that holds.

## The dockets feature

- Column sets for ambient/chilled and the signature roles per type live in
  `apps/dockets/constants.py` and are served at `/api/dockets/meta/`. The
  frontend builds its forms from that response — never hardcode column lists in
  React.
- `Docket` is one model for all four types with nullable type-specific fields;
  `DocketLine` covers both shapes (category `amounts` JSON vs item
  qty/description/cost/retail). Type rules are enforced in `DocketSerializer.validate`.
- `Docket.total` is always recomputed from the lines (`recalculate_total`); a
  client-supplied header total is ignored.
- Nested writes are replace-on-write: posting `lines` replaces the whole set.
  Omitting the key leaves the existing rows alone.
- Signatures and photos are posted as `data:` URLs and decoded by
  `Base64ImageField`. On read, that field returns a **root-relative** `/media/...`
  URL on purpose — an absolute one would carry the internal Docker hostname.
- The trading week is Sunday→Saturday, defined in both `apps/dockets/filters.py`
  and `src/features/dockets/format.ts`. Change one, change the other.
- Export uses `?output=pdf|json`, never `?format=` — DRF reserves `format` for
  content negotiation and returns 404 for an unknown renderer.
- PDF rendering is server-side (ReportLab, `apps/dockets/pdf.py`). Do not add a
  browser-side PDF library.

## Frontend conventions

- Vite + React 19 + TypeScript, strict mode on. `@/` aliases `src/` — the alias
  is declared in both `vite.config.ts` and `tsconfig.app.json`; changing one
  means changing the other.
- Server state goes through TanStack Query; auth state through `AuthContext`.
  Do not add Redux or another global store without a reason.
- All HTTP goes through `api` from `@/lib/apiClient` — it attaches the JWT and
  handles 401 refresh. Never call `axios` directly except inside that module.
  Use `apiErrorMessage(err)` to surface DRF errors.
- Feature code lives in `src/features/<name>/` (API calls, hooks, screens);
  route-level pages in `src/pages/`; routes registered in `src/router.tsx`
  under the `ProtectedRoute` → `AppLayout` branch unless deliberately public.
- Backend types are hand-written in `src/types/api.ts` and must match the
  serializer. The generated OpenAPI schema at `/api/schema/` is the reference.
- Linting is `oxlint` (`npm run lint`), not ESLint — `eslint-disable` comments
  do nothing here.
- Requests use relative `/api` paths so the Vite proxy handles them; do not
  hardcode `http://localhost:8000`. `/media`, `/admin` and `/static` are proxied
  too — add any new backend-served prefix to both `vite.config.ts` and
  `frontend/nginx.conf`.
- Styling is token-driven: `src/styles/tokens.css` holds every colour, size and
  radius; `components.css` holds the shared classes. Do not write a raw hex
  value in a component — add or reuse a token.
- Reusable UI lives in `src/components/ui/`. React contexts go in their own
  lowercase module (`authContext.ts`, `toastContext.ts`) so the provider file
  exports only components — Fast Refresh needs that, and a `Foo.tsx`/`foo.ts`
  pair would collide on macOS's case-insensitive filesystem.
- Downloads go through `downloadExport` in `features/dockets/api.ts`: axios with
  `responseType: 'blob'` so the JWT is attached. A plain `<a href>` to the API
  would be unauthenticated.

## Gotchas

- `backend/entrypoint.sh` must stay executable on the host (`chmod +x`) — the
  bind mount shadows the image's copy.
- Adding an npm package requires rebuilding the frontend image; `node_modules`
  is an anonymous volume, not bind-mounted.
- Postgres is published on host port **5433**, not 5432.
