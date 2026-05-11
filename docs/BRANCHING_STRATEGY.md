# Branching Strategy

## Overview

This repository uses a **simplified GitFlow** branching model with two long-lived branches and short-lived feature branches. Work is divided into two categories: **platform infrastructure** and **idiom (visualization) development**.

## Branch Structure

```
main
  └── develop
        ├── platform/*
        └── idiom/*
```

### Long-Lived Branches

| Branch | Purpose | Rules |
|--------|---------|-------|
| `main` | Stable, deployable version | No direct pushes. Merge only from `develop` via Pull Request at milestones. |
| `develop` | Integration branch for daily work | All feature branches merge here via Pull Request with at least 1 review. |

### Feature Branch Prefixes

| Prefix | Purpose | Example |
|--------|---------|---------|
| `platform/` | Platform infrastructure work | `platform/api-auth`, `platform/database` |
| `idiom/` | Visualization idiom development | `idiom/P1-dfg-visualization` |
| `fix/` | Bug fixes | `fix/cookie-auth-issue` |

## Team Roles & Branches

Each team member owns one platform area and a set of idioms (~4-5 each, totaling 23 idioms).

| Member | Platform Branch | Scope |
|--------|----------------|-------|
| **P1** | `platform/api-auth` | Backend API routes, authentication, cookie handling, UI tracking storage |
| **P2** | `platform/database` | MongoDB/Redis data models, database connection, CRUD operations |
| **P3** | `platform/frontend-flow` | Frontend page routing, participant experiment flow (welcome → questionnaire → end) |
| **P4** | `platform/admin-panel` | Admin dashboard (frontend + backend), dataset management, file upload/download |
| **P5** | `platform/infra-viz-framework` | Docker deployment, CI/CD, visualization display framework, user tracking collection |

For idiom branches, use the format: `idiom/<member>-<idiom-name>`, e.g.:
- `idiom/P1-petri-net`
- `idiom/P3-token-replay`

## Platform Merge Order

Platform branches have dependencies. Merge into `develop` in the following order:

```
P2 (database) → P1 (API + auth) → P3 (frontend flow) → P4 (admin) → P5 (infra + viz framework)
```

- P1 depends on P2 (API routes call database functions)
- P3 depends on P1 (frontend calls backend API)
- P4 depends on P1 + P2 (admin uses API and database)
- P5 depends on P3 (viz framework integrates into frontend pages)

Idiom development should begin **after** the platform branches have been merged into `develop`.

## Workflow

### Starting a New Feature

```bash
git checkout develop
git pull origin develop
git checkout -b platform/your-branch-name   # or idiom/your-branch-name
```

### During Development

```bash
git add .
git commit -m "meaningful commit message"
git push -u origin platform/your-branch-name
```

### Merging into develop

1. Push your branch to the remote
2. Open a **Pull Request** on GitHub targeting `develop`
3. Request at least **1 teammate** to review
4. After approval, merge the PR (use "Squash and merge" for clean history)
5. Delete the remote branch after merging

### Releasing to main

At project milestones (e.g., platform complete, all idioms done):

1. Open a Pull Request from `develop` → `main`
2. All team members review and approve
3. Merge the PR

## Branch Protection Rules (GitHub Settings)

Configure these under **Settings → Branches → Branch protection rules**:

### `main`
- ✅ Require a pull request before merging
- ✅ Require 1 approval
- ✅ Do not allow bypassing the above settings

### `develop`
- ✅ Require a pull request before merging
- ✅ Require 1 approval

## Files NOT to Commit

The following files are for local development only and should not be committed:

- `.env` (contains database credentials)
- `docker-compose.override.yml` (local volume path overrides)
- `venv/` (Python virtual environment)
- `node_modules/` (npm packages)

Make sure these are listed in `.gitignore`.
