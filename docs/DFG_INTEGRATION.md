# DFG Service Integration

How the previous team's DFG (Directly-Follows-Graph) tool coexists, in this
repo and in production, with the idiom-based Conformance Experiment Platform
built on top of it. Written after the Sept 10 extraction
(`055ebc1` → `18618a4`) that moved the DFG code out of `provibackend` /
`ProViFrontend` into a standalone `dfg-service/`.

**Short version:** the two codebases are fully independent; the two *deployments*
share an origin, a Mongo database and a Redis instance. That sharing used to let
the DFG study write into this study's data — see
[Runtime isolation](#runtime-isolation-what-used-to-leak-and-what-closed-it) for
what leaked and what now separates them.

## What is what

- **Previous project — ProVi (inherited, unchanged in substance):** its DFG study —
  `dfg-service/backend/DfgBackend` (FastAPI, `FilterModel/`, `MentalMapModel/`)
  and `dfg-service/frontend` (Next.js: graph view + questionnaire). Present
  since the repo's initial commit (`9967cb4`, 2026-03-09) as
  `provibackend/ProViBackend/FilterModel` and the original `ProViFrontend`
  admin/graph components; copy-first-extracted into its own service on
  2026-09-10.
- **Our project — ProCon (built on top):** the idiom-based experiment platform —
  `provibackend/` (tasks, idioms, answer formats, admin experiment wizard)
  and `ProViFrontend/`'s `admin/experiments/*` flow. The directory names are
  legacy from forking ProVi's repo; the code in them is ProCon.

Both are now separate codebases with no shared source, but they are deployed
together and integrated at the infrastructure level.

## Deployment topology

One `docker-compose.yml` at repo root runs both stacks side by side, sharing
`mongo` and `redis`:

| Service | Build context | Role |
|---|---|---|
| `provibackend` | `./provibackend` | our project's API |
| `provifrontend` | `./ProViFrontend` | our project's UI |
| `dfgbackend` | `./dfg-service/backend` | previous project's API |
| `dfgfrontend` | `./dfg-service/frontend` | previous project's UI |
| `mongo`, `redis` | — | shared by all four |
| `nginx` | `./provibackend/nginx` | single entry point, path-based routing |

## Request routing (nginx)

`provibackend/nginx/nginx.conf` fronts everything on one origin. That means one
cookie jar and one `localStorage` for both apps, so browser-side state is only
kept apart by naming (see Runtime isolation below). Today only cookies actually
collide — the DFG frontend uses no `localStorage` at all, ours uses it for
`adminAuthed` / `currentQuestionnaire`.

| Path | Routed to | Notes |
|---|---|---|
| `/` | `provifrontend` | landing page has cards for both studies |
| `/api/`, `/api/admin/` | `provibackend` | admin path is Basic-Auth gated |
| `/dfg/` | `dfgfrontend` | prefix **kept** (not stripped) — `dfg-service/frontend/next.config.mjs` sets `basePath: "/dfg"` and expects it |
| `/dfg/api/`, `/dfg/api/admin/` | `dfgbackend` | prefix **stripped** before proxying; admin path Basic-Auth gated with the same `.htpasswd` as the main admin area |

The landing page (`ProViFrontend/provi-frontend/src/app/page.js`) links to
the DFG study via a plain `<a href="/dfg/admin">` card ("Participate in the
study on Directly-Follows-graph visualizations") — that's the entire
frontend-level integration; there's no shared component or navigation state
between the two apps beyond that link.

## Runtime isolation: what used to leak, and what closed it

Both backends connect to the *same* Mongo database (their
`utils/database/connection.py` files started out byte-identical — copy-first
extraction):

```
mongodb://...@mongo:27017/TeamProject?authSource=admin
```

so nothing but naming keeps the two studies' data apart. Two leaks existed,
both one-directional into *this* study's data and both silent. They are now
closed; the rules below are what keeps them closed.

### Rule 1 — every DFG collection is prefixed `Dfg`

`dfg-service` had already renamed `User`/`Dataset` → `DfgUser`/`DfgDataset`,
but its answer and UI-log writes still went to the unprefixed `Answer` and
`UILogging` — the exact collections this study writes participant answers and
tracking events into. Meanwhile this study's bulk exports
(`provibackend/.../admin.py:359` `generate_csv_for_download`, called with
`query={}`) dump those collections whole, with no field saying which study a
row came from. So "download Answers" handed the admin a CSV of both studies'
rows, with columns that shift depending on which rows are present (the two
answer schemas diverged in the 2026-09-09 answer-format refactor).

Fixed by pointing `dfg-service`'s writes at `DfgAnswer` / `DfgUILogging` and
its own exports at the same (`connection.py`, `admin.py`). The dead helpers
that still wrote to `User`, `Dataset`, `KnowledgeAnswers`, `Experiment` and
`UserAssignment` — uncalled by any DFG router, but one stray call away from
writing into this study — were deleted rather than left as a trap.

### Rule 2 — the two studies never share a session cookie

Both apps set a cookie named `provi_user_id`, neither with a `path`, on one
origin. Whichever study a participant opened last therefore owned the
identity for the whole site — and this study's write endpoints take the cookie
value as the `user_id` verbatim, with no check that it was ever issued here.
A participant who opened the DFG card on our own landing page
(`ProViFrontend/.../app/page.js`) mid-study and came back would have their
next answer stored under a DFG user id: a row joinable to no `User`,
`PreliminaryAnswers` or `KnowledgeAnswers` record, with no error raised.

Fixed on both sides:

- `dfg-service` issues and reads `dfg_user_id` (`auth.py`, `vis.py`,
  `questionnaire.py`, `ui_tracking.py`), so its cookie can no longer be
  mistaken for ours.
- This study now rejects a cookie it did not issue: `dbc.user_exists()`
  (`provibackend/.../utils/database/connection.py`) gates the four endpoints
  that write cookie-keyed data — `POST /survey/answer`, `POST /auth/knowledge`,
  `POST /auth/feedback`, `POST /participant/assignment` — with a 401. This is
  belt-and-braces after the rename, but it is what catches a `provi_user_id`
  cookie still sitting in a participant's browser from a *pre-rename* DFG
  session (they live 1 day).

For this guard to be worth anything it has to be visible, which it was not at
first: `TaskAnswerPanel.js`'s submit handler advanced the participant from a
`finally` block, regardless of whether the POST succeeded, so any 401 —
including one from this guard — dropped that answer with only a `console.error`.
Fixed in the same session: the trial now advances only after a 2xx, and a failed
submit keeps the rating modal open with a retry (see `submitWithRatings`).

### Still shared, deliberately or harmlessly

- **Admin credentials.** `/admin` and `/dfg/api/admin/` use the same
  `.htpasswd`, so one login covers both admin UIs. Intentional.
- **Redis.** One instance, flat keyspace, no key prefix in either service —
  but only `dfg-service` actually writes keys; `provibackend` imports
  `redis_handler` (`admin.py:66`) and never calls it. Not a live collision;
  would become one if this study starts using Redis without prefixing.
- **Schema lineage.** `dfg-service`'s copies of the shared models are frozen
  at extraction time and will drift from `provibackend`'s as the latter
  evolves. Expected, now that the collections are disjoint — but it means
  "the same model name" in the two services no longer implies the same shape.

## Data volume: mount looks shared but isn't actually used by dfg-service

`docker-compose.yml` mounts the same host path for both backends'
`data` volumes:

```
provibackend: /srv/provi-data → /code/ProViBackend/data
dfgbackend:   /srv/provi-data → /code/DfgBackend/data
```

In practice `dfg-service`'s `admin.py` never reads or writes under
`config.BASE_DIRECTORY / "data"` — uploads and generated visualizations go to
`config.BASE_DIRECTORY / "output"` (`/code/DfgBackend/output`), which is not the
mounted path at all. Two consequences:

- The shared host path is inert for `dfg-service`, so the two services do **not**
  in fact share a data directory — even though the compose file reads as if they
  do, which is misleading in exactly the direction that matters here.
- Nothing `dfg-service` generates survives container recreation — and
  `.github/workflows/deploy.yml` force-removes the `dfgbackend` container
  (`docker rm -f … dfgbackend dfgfrontend`) on **every** deploy to `develop`.
  So each deploy wipes every DFG dataset and SVG; an admin has to re-upload and
  re-activate, and any participant mid-study gets 404s on their visualization.
  (`mongo` is removed too but keeps its named volume, and `provibackend`'s data
  lives on the `/srv/provi-data` host path, so only DFG loses state.)

Deliberately not fixed: the damage is confined to the DFG tool and never reaches
ProCon's data, so an admin re-uploading after a deploy is the accepted cost. The
one-line fix, should the DFG study ever start collecting real participant data:
point `dfgbackend`'s volume at `output/` instead of `data/`.

## Rough edges from the extraction (fixed, but a checklist for next time)

The copy-first extraction was iterated on the same day it landed, in this
order — worth using as a checklist for extracting other previous-project
modules the same way:

1. `055ebc1` — copy code into `dfg-service/`
2. `ced5edc` — missing frontend deps surfaced at build time (`react-zoom-pan-pinch`, `@mui/icons-material`, `@coreui/react`)
3. `dfbede8` — dataset upload/activation pipeline had been dropped, restored
4. `b150a39` — the copied admin page had been replaced by a placeholder test page, restored
5. `d0d586d` — missing `autoprefixer` surfaced at build time
6. `dcc23d5` — static assets 404'd until `basePath` was set and nginx stopped stripping `/dfg/`
7. `7c574fb`, `ca4492f` — original logo/favicon restored (had been dropped/replaced)

Recorded retroactively in `CHANGES.md` under
*Session: DFG Study Extracted Into a Standalone Service (2026-09-10)*, since
every other cross-cutting change in this repo has an entry there.

## Open follow-ups

1. **Rows written before the rename are still in the shared collections.** The
   code no longer mixes the two studies, but DFG rows already in `Answer` /
   `UILogging` stay there and still show up in this study's bulk CSV exports.
   Note that only *part* of each collection is affected — ProCon's own rows are
   interleaved and must survive — and that separability depends on when a row
   was written:

   - **After the 2026-09-10 extraction:** reliably identifiable. `dfg-service`
     registers participants in `DfgUser`, so a row is DFG's exactly when its
     `user_id` appears there.
   - **Before the extraction**, while the DFG code still lived inside
     `provibackend`: *not* separable that way. It shared this app's
     `create_user` / `create_answer` helpers, so its participants went into
     `User` alongside ours; telling those rows apart needs field shape or
     timestamps.

   Nothing was touched — deciding to move or delete is a call on live data, and
   the volume is unknown from outside the deployment. Sensible order: a
   read-only inspection first (how many rows, which of the two kinds), then a
   one-off script in the style of `scripts/drop_ground_truth_data.py`
   (`--dry-run` / `--yes`).
