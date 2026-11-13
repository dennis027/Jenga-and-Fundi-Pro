# Git history

This repository was created by consolidating three repositories with
`git subtree add` (**without** `--squash`), so every original commit (message, author,
dates) is kept. Each import is a merge commit whose second parent is that repository's
`main`.

| Prefix | Original repository | Commits | Hashes |
|---|---|---|---|
| `backend/` | github.com/dennis027/jenga-backend (`main`) | 47 | **rewritten** by the purge below |
| `frontend/fundi-pro/` | github.com/dennis027/new-fundi-pro (`main`) | 48, incl. 3 never pushed | unchanged |
| `frontend/jenga-pro/` | github.com/dennis027/new-jenga-pro (`main`) | 31, incl. 1 never pushed | partly rewritten (redaction, below) |

The original working copies (including `node_modules`, the old `venv`, the gitignored
`.env` and the stash lists) were moved, untouched, to `../fundi-jenga-pro-original-repos/`.
Nothing was pushed to or deleted from any remote. The remotes' `gh-pages` branches
(GitHub Pages builds) were not imported.

## Personal-data purge (2026-11-14)

The backend repo had committed user uploads: national ID photos (front/back), selfies,
payment screenshots and OCR scratch images. They were removed from **every commit and tag**
with [git-filter-repo](https://github.com/newren/git-filter-repo):

```bash
git filter-repo --force --invert-paths --prune-empty never \
  --path MEDIA/ --path temp/ --path backend/MEDIA/ --path backend/temp/
git filter-repo --force --invert-paths --prune-empty never \
  --path payments/ --path backend/payments/          # older upload location
```

Before the repository went public, a third pass redacted the original hardcoded Django
`SECRET_KEY` and two personal phone numbers (a Twilio/SMS test recipient in old backend code,
and a sample-data number in jenga-pro's `manage-workers.ts`) from every commit:

```bash
git filter-repo --force --prune-empty never --replace-text redact.txt
#   regex:django-insecure-\+0q4\+wo03[^'"\s]*==>django-insecure-REDACTED
#   literal:<phone>==>+254700000000      literal:<phone>==>0700000000
```

That old key must be treated as compromised either way. Rotate it wherever it is still in use (Render).

- `--prune-empty never` keeps every commit, including ones that only added uploads, so no
  commit message is lost. All 173 commits and 17 tags still exist.
- The rewritten objects were expired and repacked. The files are not recoverable from this
  repository, and `.git` shrank from 7.7 MB to 2.8 MB.
- Backend commits, part of jenga-pro's history, and everything after them have **new hashes**
  (101 of 173). fundi-pro's history is unchanged. Hash references inside
  commit messages were updated too. Old → new: [history-commit-map.txt](history-commit-map.txt).
- A pre-purge backup is at `../fundi-jenga-pro-original-repos/monorepo-before-history-purge.bundle`.
  It still contains the images, so delete it once you're satisfied.

**Still to do outside this repo.** `github.com/dennis027/jenga-backend` still serves these
files in its history. To remove them there, push the rewritten backend history over it:

```bash
git subtree split --prefix=backend -b backend-purged
git push --force backend-upstream backend-purged:main
```

Then ask GitHub Support to purge cached views, and check for forks. A force push rewrites
that repo's `main` for everyone who has cloned it.

## Browsing history

```bash
git log --oneline --graph                 # everything, including the three import merges
git log --oneline -- backend/             # commits after the import that touched backend/
git log --oneline <import-merge>^2        # one component's original history
```

Pre-import commits recorded paths without the prefix, so `git log -- backend/app/views.py`
stops at the import. Use `git log <import-merge>^2 -- app/views.py` for older history.

## Archived stashes

All 17 stashes (15 backend, 1 fundi-pro, 1 jenga-pro) are preserved as tags:
`archive/stash/<backend|fundi-pro|jenga-pro>/NN` (`NN` = the original `stash@{NN}` index).
Their paths are relative to the original repo root. To re-apply one:

```bash
git diff archive/stash/backend/00^1 archive/stash/backend/00 | git apply --directory=backend
```

## Upstream remotes

`backend-upstream`, `fundi-pro-upstream` and `jenga-pro-upstream` point at the original
GitHub repos (no `origin` is configured yet). fundi-pro still shares history with its upstream.
jenga-pro shares it only up to the first redacted commit:

```bash
git subtree pull --prefix=frontend/fundi-pro fundi-pro-upstream main
git subtree push --prefix=frontend/jenga-pro jenga-pro-upstream main
```

The backend no longer shares hashes with `backend-upstream` unless you force-push the purged
history there (see above). The simplest path is to treat this monorepo as the backend's new
home and archive the old repo.

To publish the monorepo, create a new **private** GitHub repository and
`git remote add origin <url> && git push -u origin main --tags`.
