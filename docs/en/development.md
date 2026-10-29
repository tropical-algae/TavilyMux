# Local Development Guide

This guide covers the local development environment, startup workflow, and quality checks for TavilyMux.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 24
- npm

## Install Dependencies

Run the following commands from the project root:

```bash
uv sync --frozen
npm --prefix web ci
```

Backend dependencies are installed in the project's `.venv`, while frontend dependencies are installed in `web/node_modules`.

To use custom development configuration, copy either of the example files as needed:

```bash
cp .env.example .env
cp config.yaml.example config.yaml
```

Environment variables take precedence over `.env` and `config.yaml`. Locally generated databases, master keys, and runtime data are stored in `data/` by default.

## Start the Development Environment

**Start the backend:**

```bash
uv run poe run
```

The backend listens on `http://127.0.0.1:8080` by default. If `TAVILY_MUX_ADMIN_SECRET` is not configured on first startup, the randomly generated management key is printed in the terminal logs.

**Start the frontend:**

```bash
npm --prefix web run dev
```

Open `http://localhost:5173`. Vite proxies `/api`, the built-in Tavily endpoints, `/livez`, and `/readyz` to the local backend. Test configured custom endpoints directly through `http://localhost:8080`.

## Test the Production Frontend Locally

Build the frontend and serve its static files directly from FastAPI:

```bash
npm --prefix web run build
TAVILY_MUX_WEB_ROOT=web/dist uv run poe run
```

The Web console and API are now both available at `http://localhost:8080`, matching the production image behavior.

## Quality Checks

Run all backend checks, tests, and the frontend build:

```bash
uv run poe test-all
```

You can also run each check separately:

```bash
uv run poe lint
uv run poe format-check
uv run poe type-check
uv run poe test

npm --prefix web run lint
npm --prefix web run format-check
npm --prefix web run type-check
npm --prefix web run test
npm --prefix web run build
```

Before committing, run the complete pre-commit suite:

```bash
uv run pre-commit run --all-files --show-diff-on-failure
```

## Docker Build

Build the production image from the project root:

```bash
docker build -t tavilymux:local .
```
