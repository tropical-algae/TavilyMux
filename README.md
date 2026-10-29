<div align="center">
  <img width="112" src="web/public/tavily-mux.svg" alt="TavilyMux Logo" />
</div>
<div align="center">
  <img src="web/public/tavily-mux-name.svg" alt="TavilyMux" />
</div>
<p align="center"><strong>A high-performance, self-hosted Tavily key pool and transparent search gateway</strong></p>
<p align="center">
  <a href="https://github.com/tropical-algae/TavilyMux/actions/workflows/ci.yaml"><img src="https://github.com/tropical-algae/TavilyMux/actions/workflows/ci.yaml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/tropical-algae/TavilyMux/actions/workflows/release.yaml"><img src="https://github.com/tropical-algae/TavilyMux/actions/workflows/release.yaml/badge.svg" alt="Release" /></a>
  <a href="README_CN.md"><img src="https://img.shields.io/badge/README-简体中文-red.svg" alt="README-简体中文" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License" /></a>
</p>

TavilyMux organizes multiple Tavily keys into isolated account pools and provides a unified API gateway through a Tavily Search-compatible interface.

The service selects an available key according to each pool's routing policy, performs controlled failover when an upstream request fails, and includes quota monitoring, request logs, and a Web management console.

## Features

- **Multiple account pools**: Configure multiple isolated pools, each with its own routing policy, connection settings, and relay credentials.
- **In-memory routing**: Choose between two routing strategies.
- **Failover**: Cool down or disable unhealthy keys according to the upstream error type, then select another available key when permitted.
- **Quota monitoring**: Periodically query Tavily Usage and display key-level and account-level quotas.
- **Observability**: Record request outcomes, internal attempts, latency, and key usage.
- **Proxy support**: Configure global or pool-level HTTP/HTTPS proxies, including services such as Clash.
- **Secure storage**: Encrypt Tavily keys and proxy credentials while storing only hashes or digests of management and relay keys.

## Getting Started

The TavilyMux Web console, management API, and Search relay share port `8080`. Once the service is running, open [`http://localhost:8080`](http://localhost:8080).

<details>

<summary><strong>🐳 Docker Setup</strong> - Click to expand</summary>

</br>

Create a persistent data directory and start the container:

```bash
mkdir -p data

docker run -d \
  --name tavilymux \
  --restart unless-stopped \
  -p 8080:8080 \
  -v "$(pwd)/data:/data" \
  -e TAVILY_MUX_ADMIN_SECRET='an administration key of at least 12 characters' \
  tropicalalgae/tavilymux:latest
```

</details>

<details>

<summary><strong>📦 Docker Compose Setup</strong> - Click to expand</summary>

</br>

```bash
mkdir -p data
docker compose up -d --build
```

Compose runs a standalone Nginx instance in front of TavilyMux, with Nginx exposing the service port.

Nginx handles Gzip compression, timeouts, and streaming response buffering policy, but it is not a functional dependency of TavilyMux.

When the application image is run on its own, the Web console and all APIs remain fully available. If your deployment already uses Caddy, Traefik, Nginx, or a cloud gateway, you can use the Docker setup directly.

</details>

> [!IMPORTANT]
> `TAVILY_MUX_ADMIN_SECRET` is used only to initialize the management key on first startup.
> If it is not configured, TavilyMux generates a random management key and prints it in the logs.

## Configuration

TavilyMux can load configuration from environment variables, an [.env](.env.example) file, and a [config.yaml](config.yaml.example) file. The default configuration file path is `/data/config.yaml`. The key settings are listed below:

| YAML field               | Environment variable                | Description                                                                                          |
| ------------------------ | ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `ADMIN_SECRET`           | `TAVILY_MUX_ADMIN_SECRET`           | Management key used during first-time initialization; must contain at least 12 characters            |
| `MASTER_KEY`             | `TAVILY_MUX_MASTER_KEY`             | Optional encryption master key; normally generated automatically and persisted at `/data/master.key` |
| `COOKIE_SECURE`          | `TAVILY_MUX_COOKIE_SECURE`          | Set to `true` when serving TavilyMux over HTTPS                                                      |
| `DATABASE_URL`           | `TAVILY_MUX_DATABASE_URL`           | Uses `/data/database.db` by default and normally does not need to be changed                         |
| `MAX_REQUEST_BODY_BYTES` | `TAVILY_MUX_MAX_REQUEST_BODY_BYTES` | Maximum Search request body size                                                                     |
| `GLOBAL_MAX_CONCURRENCY` | `TAVILY_MUX_GLOBAL_MAX_CONCURRENCY` | Maximum global concurrency for a single instance                                                     |

If the management key is lost, generate a new one and revoke all existing login sessions:

```bash
# Docker deployment:
docker exec -it tavilymux tavily-mux reset-admin-secret
# Compose deployment:
docker compose run --rm app reset-admin-secret
```

## Local Development

Local development requires Python 3.13, uv, Node.js 24, and npm.
See the [local development guide](docs/en/development.md) for dependency installation, backend and frontend startup, testing, and build instructions.

## Current Limitations

- [ ] Support Tavily Extract, Crawl, Map, and Research endpoints in addition to Search.
- [ ] Support multiple Uvicorn workers or replicas; routing state, concurrency control, and key cooldown state currently live in the memory of a single instance.
- [ ] Support external persistent databases such as PostgreSQL.
- [ ] ~~Support multiple administrators, role-based access control, and isolated management spaces; the service currently uses a single management key.~~
- [ ] Provide integrated backup and restore tooling for account pools, configuration, and encrypted data.
- [ ] Provide Prometheus metrics, OpenTelemetry traces, and more comprehensive runtime alert integrations.
- [ ] Provide built-in HTTPS certificate management; TLS should currently be terminated by Nginx, Caddy, Traefik, or a cloud gateway.

## License

TavilyMux is released under the [MIT License](LICENSE).
