# CLAUDE.md

## What this is — and isn't

The demo consumer of `transparent-fastapi`. **NOT part of the published library.** It exists to:

1. Be the FastAPI app baked into the docker image at `Dockerfile`.
2. Give locust something to point at via `deploy/source/scripts/deploy.sh load-medium` / `load-high`.

Don't add library features by editing `app.py` here. Library code lives in `../transparent_fastapi/`.

## Why a separate `pyproject.toml`

uv workspaces require each member to have one. This pyproject just declares workspace membership and a path-source dep on `transparent-fastapi`. **No `[build-system]`** because we never build a wheel for this directory — the Dockerfile installs the library + uvicorn directly and copies `app.py` in. Adding a build system would force packaging machinery for no benefit.

## Why no `__init__.py`

The Dockerfile copies `app.py` to `/app/app.py` (flat, no nested package) and runs `uvicorn app:app`. Works via namespace packages (Python 3.3+). Adding `__init__.py` here would make the import path `test_server.app:app`, which would force the Dockerfile to also `pip install` this directory — extra ceremony for zero gain.

## What endpoints should/shouldn't be here

The two `/sleep-async` and `/sleep-sync` routes are deliberate: they're the headline demo of event-loop blocking vs non-blocking. The locust profiles in `deploy/source/locustfile.py` (`MediumLoadUser` / `HighLoadUser` — both subclasses of `_BaseTrafficUser`, which holds the shared task weights) use `/sleep-async` but not `/sleep-sync` — `/sleep-sync` is kept around for ad-hoc curl demos of the loop-lag spike. `/health` is excluded from metrics by `install(app, excluded_paths=["/health"])` — that's the intended demonstration of the `excluded_paths` kwarg.

If you want to demo a new library feature under load, add a route here. If you want to demo it in documentation, prefer the README.
