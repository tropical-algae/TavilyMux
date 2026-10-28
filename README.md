# TavilyMux

[中文](README_CN.md)

A self-hosted Tavily API-key pool with a transparent, high-concurrency `/search` relay and a Web management console.

## Highlights

- Schema-free Tavily Search forwarding: unknown request/response fields pass through unchanged.
- In-memory `max remaining quota` or `random available key` routing with automatic failover.
- Multiple isolated pools and rotatable relay keys.
- Encrypted Tavily keys and proxy credentials; hashed management and relay keys.
- Periodic `/usage` monitoring, quota timelines, request/attempt logs, and current alerts.
- Global or pool-level Tavily URL and Clash-compatible HTTP/HTTPS proxy settings.
- SQLite persistence, asynchronous batched event writes, Docker, Nginx, CI, and semantic releases.

## Run with Docker Compose

```bash
docker compose up --build -d
docker compose logs app
```

Open `http://localhost:8080`. On a brand-new data volume, set `TAVILY_MUX_ADMIN_SECRET` in `.env`; if omitted, the service generates a strong management key and prints it once in the app log.

Data and the generated encryption key live in the `tavily-mux-data` volume. Back up the whole volume—`database.db` is unusable without `master.key`.

If Clash runs on the Docker host, use a proxy URL such as `http://host.docker.internal:7890`. Compose maps that hostname on Linux as well.

## Search relay

Create a pool, add Tavily keys, then copy its one-time relay key:

```bash
curl http://localhost:8080/search \
  -H 'Authorization: Bearer tpool_your_relay_key' \
  -H 'Content-Type: application/json' \
  -d '{"query":"latest Python release","search_depth":"advanced"}'
```

The service only reads the relay authorization, replaces it with a selected Tavily key, and forwards the raw query string, body, supported headers, status, response headers, and response stream. It does not define Tavily's Search schema locally.

## Configuration

Startup settings support environment variables, `.env`, and YAML with this precedence:

```text
environment > .env > config.yaml > defaults
```

See [.env.example](.env.example) and [config.yaml.example](config.yaml.example). Runtime Tavily URL, proxies, monitoring interval, timeout, failover attempts, and retention are managed in the Web console.

Reset a lost management key from the deployment environment; this also revokes existing sessions:

```bash
docker compose run --rm app reset-admin-secret
# or: tavily-mux reset-admin-secret --secret 'a-new-long-management-key'
```

The generated value is shown once. Passing a secret on the command line can expose it in shell history, so generation is preferred.

## Local development

Requirements: Python 3.13, `uv`, Node.js 24, and npm.

```bash
uv sync --frozen
npm --prefix web ci
uv run poe test-all
uv run poe run
```

Run the Vite development server separately with `npm --prefix web run dev`. Build the production console with `npm --prefix web run build` and set `TAVILY_MUX_WEB_ROOT=web/dist` when serving it directly from FastAPI.

Useful commands:

```bash
uv run poe lint
uv run poe type-check
uv run poe test
npm --prefix web run lint
npm --prefix web run type-check
npm --prefix web run test
npm --prefix web run build
```

## Deployment notes

- V0.1 intentionally uses one service instance and one Uvicorn worker. In-memory routing and rate state are not shared across workers or replicas.
- Nginx disables response buffering for `/search`; do not add a buffering proxy in front of it if streaming latency matters.
- Set `TAVILY_MUX_COOKIE_SECURE=true` behind HTTPS.
- Do not expose the app container port directly when Nginx is the public entry point.
- Tavily keys, relay keys, proxy passwords, and full search bodies are not written to product request logs.

## License

[MIT](LICENSE)
