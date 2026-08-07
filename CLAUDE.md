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
- Departments narrow it further: a staff user sees their own department in
  their own store and nothing else — see the Departments section below. Their
  store and their department's store are kept in step, so the two scopes can
  never point at different branches.
- Frontend locks (disabled store pickers, hidden "All stores", hidden Team nav)
  are UX only. The API is the boundary; add both when adding a scoped screen.
- Only an admin can grant or revoke the admin role, and nobody can change their
  own role or deactivate themselves (`TeamMemberSerializer`).
- `/api/auth/bootstrap-admin/` creates an admin from a shared code
  (`ADMIN_BOOTSTRAP_CODE`), for first setup without shell access. It 404s when
  the variable is unset, compares the code with `secrets.compare_digest`, and is
  rate limited via the `admin_bootstrap` throttle scope. It must only ever
  create admins — never widen it to other roles or make it authenticated-optional
  in some other way.
- Emails are stored lower-cased and sign-in is case-insensitive
  (`apps/accounts/auth_serializers.py`). Keep new user-creation paths going
  through `UserManager.create_user` so that holds.

## Departments

Two levels, and the distinction is the whole feature:

- `Department` is the *kind* — "the Deli", group-wide. Nobody is assigned to one.
- `StoreDepartment` is that kind in one branch — "Deli · Balbriggan". This is
  what `User.department` points at, so every roster is store specific.
  Unique per `(department, store)`.

Rolling the branches of one kind back up is what answers "the Deli in general";
reading a single branch is what a staff user is allowed to see.

- **A store runs a department or it does not, and that is the presence of a
  `StoreDepartment` row.** There is deliberately no separate "closed" flag to
  drift out of step with it. `DepartmentSerializer.create` opens a new kind in
  the stores named in `store_slugs`, defaulting to all of them; after that an
  admin adds and removes stores one at a time by POSTing to and DELETEing from
  `/api/departments/in-stores/`. A newly added `Store` needs its branches
  opened by hand.
- `DepartmentSerializer.update` **drops `store_slugs`**. Which stores run a
  department is only ever edited per store — a slug missing from a resubmitted
  list must never silently delete a branch and its roster.
- A branch's `department` and `store` are write-once: `get_fields` removes both
  slug fields once there is an instance, because moving a branch would drag its
  whole roster into a store those people do not work in.
- Slugs are generated once and never regenerated (`build_unique_slug`), so a
  rename keeps existing links working. A branch slug is
  `<department>-at-<store>`, but nothing outside the API composes it — the
  frontend resolves `/departments/:slug/:storeSlug` through
  `useStoreDepartmentAt`, which filters the list endpoint.
- Endpoints, both unpaginated reference data keyed by `slug`:
  - `/api/departments/` — kinds, with `member_count`/`store_count` pooled across
    branches. `IsManagerReadAdminWrite`: **staff get 403 on the whole
    resource**, because pooling stores is exactly what they must not see.
    Detail adds `stores` (the per-branch breakdown), `roles` and the combined
    `members`.
  - `/api/departments/in-stores/` — branches. Everyone signed in reads it, but
    `get_queryset` narrows a staff user to `pk == user.department_id` — not
    other departments in their store, not the same department elsewhere. Writes
    are admin-only. `StoreDepartmentSerializer.Meta.validators` is emptied so
    the friendly "Balbriggan already runs Deli" wins over DRF's auto
    unique-together message; the database constraint is still the backstop.
- `roles` is `{staff, manager, admin, total}` over **active** members, built by
  `serializers.role_breakdown`. The same shape is reported for one branch and
  for the group, so `RoleTiles` renders both.
- Serializer choice is a query-count decision. `StoreDepartmentLabelSerializer`
  (no counts) is what nests on a user — the counts read the roster, and a
  25-row team page would otherwise fire 25 extra queries.
  `StoreDepartmentRowSerializer` adds them and is only used where the viewset
  prefetches `members` (see `views.member_prefetch`).
- `User.department` is `PROTECT`, and nullable in the database only because
  accounts predating it (and the bootstrap admin) have none.
  `TeamMemberCreateSerializer` requires `department_slug`;
  `TeamMemberSerializer` refuses to null it. Both go through
  `accounts.serializers.department_field`, which only accepts a live branch of
  a live kind.
- **`store` and `department.store` must agree**, enforced by
  `accounts.serializers.validate_store_matches_department`: picking a
  department settles the store when there is none, a mismatched pair is
  refused, and the store cannot be cleared out from under a department. The
  Team page cooperates — moving somebody between stores sends the equivalent
  branch of the same kind along with the store, and refuses in the UI when the
  destination does not run it.
- Both deletes refuse to orphan staff and 400 with the count:
  `DepartmentViewSet.perform_destroy` counts across every branch (deleting a
  kind cascades to them), `StoreDepartmentViewSet.perform_destroy` counts the
  one store. Archiving the kind (`Department.is_active`) is the soft option;
  for a single store, move the people and then remove it.
- `DepartmentsIndex` is what `/departments` renders: the group list for a
  manager, a redirect to their own branch for a staff user, an empty state for
  a staff user with no department.
- The group page's "By store" table lists **every** store, joining
  `useStores()` to `department.stores`, so the ones that do not run it are
  where an admin presses "Open here". That is also why it is not a
  `table--rows-clickable`: half the rows have no page to open.
- Both detail pages build their Details card from one `meta` array, so a new
  serializer field is one line there and nothing else.
- Not to be confused with `Docket.department`, a free-text field on transfer
  dockets. The two are unrelated for now.

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

## Rosters

- `apps/rosters` has exactly one model, `Shift`. **There is no roster record** —
  a roster is this table read for one store and one trading week, which is why
  a manager can open any week and start filling it in with nothing to create
  first, and why there is no draft state to get stuck in.
- One shift per person per day (`one_shift_per_person_per_day`). Split shifts
  would need that constraint lifted *and* the board's one-cell-per-day layout
  rethought.
- The week is the same Sunday→Saturday trading week as the top sheets —
  `apps.dockets.filters.week_start` is imported rather than redefined.
- The arithmetic lives on the model and is **never accepted from a client**:
  - `duration_minutes` — clock-in to clock-out. An end at or before the start
    reads as finishing the next day, so a 22:00–02:00 close is four hours.
  - `paid_minutes` — the span less the break, unless `break_paid`.
  - `cost` — `paid_minutes × effective_hourly_rate`, rounded **per shift**, so a
    total always equals the rows printed above it.
  `serializers.totals_for` returns the same `{shift_count, paid_minutes, hours,
  cost}` block for a person, a department and a store, so one component renders
  all three. The frontend's `paidMinutesOf` mirrors the span/break maths for the
  editor's live preview only.
- `User.hourly_rate` is nullable; `User.effective_hourly_rate` falls back to
  `settings.MINIMUM_HOURLY_RATE` (env `MINIMUM_HOURLY_RATE`, €14.20). Costing an
  unrated account at zero would be worse than useless, so it never happens.
  **Only an admin sets pay** (`validate_hourly_rate` on both team serializers),
  and never below the minimum. Managers read it because the roster prices their
  week off it.
- Cost uses the person's rate *now*, not a snapshot taken when the shift was
  written — a roster is a forward-looking plan, so a rate change is meant to
  reprice it. Change that if rosters ever become a payroll record.
- `GET /api/rosters/board/?store=&week=` assembles the week: every department
  the store runs, everyone who works there (managers included, unrostered people
  with a zero week, anyone department-less grouped last), and the totals.
  `/api/rosters/shifts/` is plain CRUD. Both are `IsManager` — a roster carries
  what everybody is paid, so staff cannot see one at all.
- `ShiftSerializer.Meta.validators` is emptied for the same reason as the
  departments one: DRF's auto unique-together message is unreadable, so
  `validate` names the person and the day instead.
- **Every rostered hour must belong to a visible row.** `Shift.store` is
  denormalised from `user.store`, so somebody who transfers or is deactivated
  keeps their shifts at the branch they worked. `collect_board` therefore adds
  anyone holding a shift that week back onto the board, and `build_board` files
  a person under a department only when that department is one this store runs
  — otherwise the store total would be quietly larger than the rows under it.
  There are tests pinning that reconciliation; keep them.
- `GET /api/rosters/export/?store=&week=&department=&output=pdf|json` renders
  the week, whole store or a few departments (`?department=deli,bakery` or
  repeated). Narrowing recomputes the totals from the kept departments only, so
  a one-department PDF reports that department's wage bill, not the store's.
  Screen and export both go through `collect_board`, so a download can never
  disagree with what the manager was looking at.
- **A board group carries two slugs and they are not interchangeable.** `slug`
  is the branch (`deli-at-balbriggan`); `department_slug` is the kind (`deli`),
  and the kind is what the export filters on. Sending the branch slug used to
  produce a perfectly valid-looking PDF of nobody, so the export now 400s on a
  slug the store does not run rather than exporting an empty week.
- `apps/rosters/pdf.py` imports its palette from `apps.dockets.pdf` so both
  exports print as the same organisation. Landscape A4, one table per
  department, header row repeated when a department splits across pages.

## Tables

- `.table th` and `.grid-table th` set a default `text-align`, and both
  out-specify a bare `.u-right` utility. `components.css` restates
  `.table th.u-right` / `.table th.u-center` for that reason — without them a
  right-aligned numeric heading silently reverts to left while its figures stay
  right, which is what every money column in the app used to do. **Any new
  alignment utility used on a `th` needs the same treatment.**
- Cells need no such override: `.table td` sets no alignment, so the utility
  already wins, and the stacked mobile layout (`.table--stacked td`) overrides
  them on purpose.
- `table--stacked` turns rows into cards on a phone and draws each cell's label
  from `data-label`. A cell whose label would read as nonsense — a `colSpan`
  spanning several columns, an action button — should simply omit `data-label`
  and take the full width.

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

## Uploads and reliability

- Signatures and photos are the only thing that touches the filesystem, and the
  only part that fails for environmental rather than input reasons. Media write
  errors must surface as `StorageUnavailable` (503, transaction rolled back),
  never a bare 500 — see `apps/dockets/serializers._write_children`.
- `/api/health/` writes a probe file, so it reports whether uploads actually
  work, and flags `media_persistent: false` when no Railway volume is mounted.
- `entrypoint.sh` runs as root purely to fix ownership of a mounted volume,
  then drops to `appuser` with `setpriv`. Do not add a `USER` line to the prod
  stage — it would break the volume fix-up.
- reportlab's `Image` is lazy. Always load upload bytes through
  `pdf._image_flowable`, which reads them eagerly inside a try/except; passing
  a path means a single missing file kills the whole export at `doc.build()`.
- Row totals on category dockets are recomputed server-side from `amounts`; the
  client's value is never trusted.

## Gotchas

- `backend/entrypoint.sh` must stay executable on the host (`chmod +x`) — the
  bind mount shadows the image's copy.
- Adding an npm package requires rebuilding the frontend image; `node_modules`
  is an anonymous volume, not bind-mounted.
- Postgres is published on host port **5433**, not 5432.
