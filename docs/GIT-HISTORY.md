# Git history

This repository was created by consolidating three repositories with
`git subtree add` (**without** `--squash`), so every original commit is kept with its
original hash. Each import is a merge commit whose second parent is the original
repository's `main`.

| Prefix | Original repository | Commits imported | Note |
|---|---|---|---|
| `backend/` | github.com/dennis027/jenga-backend (`main`) | 47 | |
| `frontend/fundi-pro/` | github.com/dennis027/new-fundi-pro (`main`) | 48 | includes 3 commits never pushed to origin |
| `frontend/jenga-pro/` | github.com/dennis027/new-jenga-pro (`main`) | 31 | includes 1 commit never pushed to origin |

The original working copies (including `node_modules`, the old `venv`, the gitignored
`.env` and the stash lists) were moved, untouched, to
`../fundi-jenga-pro-original-repos/`. Nothing was pushed to or deleted from any remote.
The remotes' `gh-pages` branches (GitHub Pages builds) were not imported.

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
GitHub repos (no `origin` is configured yet). To keep exchanging changes with them:

```bash
git subtree pull --prefix=backend backend-upstream main
git subtree push --prefix=frontend/fundi-pro fundi-pro-upstream main
```

To publish the monorepo, create a new GitHub repository and
`git remote add origin <url> && git push -u origin main --tags`.
