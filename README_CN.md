<div align="center">
  <img width="112" src="web/public/tavily-mux.svg" alt="TavilyMux Logo" />
</div>
<div align="center">
  <img src="web/public/tavily-mux-name.svg" alt="TavilyMux" />
</div>
<p align="center"><strong>高性能、自托管的 Tavily Key 池与透明搜索网关</strong></p>
<p align="center">
  <a href="https://github.com/tropical-algae/TavilyMux/actions/workflows/ci.yaml"><img src="https://github.com/tropical-algae/TavilyMux/actions/workflows/ci.yaml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/tropical-algae/TavilyMux/actions/workflows/release.yaml"><img src="https://github.com/tropical-algae/TavilyMux/actions/workflows/release.yaml/badge.svg" alt="Release" /></a>
  <a href="README.md"><img src="https://img.shields.io/badge/README-EN-blue.svg" alt="README-EN" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License" /></a>
</p>

TavilyMux 将多个 Tavily Key 组织成相互隔离的账号池，并通过兼容 Tavily Search 的接口提供统一的 API 网关

服务会按池内规则选择可用 Key，在上游请求失败时执行受控切换，同时提供额度监控、请求日志和 Web 管理控制台

## 特性说明

- **多账号池**：支持配置多个隔离的账号池，拥有独立的路由规则、连接配置和中转凭证
- **内存路由**：支持2种路由策略
- **故障切换**：根据上游错误类型冷却或停用异常 Key，并在允许的范围内选择其他可用 Key
- **额度监控**：定期读取 Tavily Usage，展示 Key 与账户额度
- **可观测性**：记录请求结果、内部尝试、耗时和 Key 使用情况
- **代理支持**：支持全局或账号池级 HTTP/HTTPS 代理，可连接 Clash 等代理服务
- **安全存储**：Tavily Key 和代理凭据加密保存，管理密钥和中转 Key 仅保存哈希或摘要

## 启动方法

TavilyMux 的 Web 控制台、管理 API 和 Search 中转共用 `8080` 端口。启动后访问
[`http://localhost:8080`](http://localhost:8080)

<details>

<summary><strong>🐳 Docker Setup</strong> - Click to expand</summary>

</br>

准备一个持久化目录，然后启动容器：

```bash
mkdir -p data

docker run -d \
  --name tavilymux \
  --restart unless-stopped \
  -p 8080:8080 \
  -v "$(pwd)/data:/data" \
  -e TAVILY_MUX_ADMIN_SECRET='至少 12 位的管理密钥' \
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

Compose 会在 TavilyMux 前运行一个独立的 Nginx，并由 Nginx 暴露服务端口

Nginx 负责 Gzip、超时和流式响应缓冲策略，但不是 TavilyMux 的功能依赖

单独运行应用镜像时，Web 控制台和所有 API 仍然完整可用。如果部署环境已经有 Caddy、Traefik、Nginx 或云端网关，可以直接使用 Docker Run 方式

</details>

> [!IMPORTANT]
> `TAVILY_MUX_ADMIN_SECRET` 只用于首次初始化管理密钥
> 如果首次启动时未配置，TavilyMux 会随机生成一个管理密钥，并在日志中显示

## 配置方法

TavilyMux 支持通过环境变量、[.env](.env.example) 和 [config.yaml](config.yaml.example) 加载配置，配置文件默认路径为 `/data/config.yaml`。关键配置项如下：

| YAML 字段                | 环境变量                            | 说明                                                               |
| ------------------------ | ----------------------------------- | ------------------------------------------------------------------ |
| `ADMIN_SECRET`           | `TAVILY_MUX_ADMIN_SECRET`           | 首次初始化使用的登录管理密钥，至少 12 位                           |
| `MASTER_KEY`             | `TAVILY_MUX_MASTER_KEY`             | 可选的加密主密钥；通常让服务在 `/data/master.key` 自动生成并持久化 |
| `COOKIE_SECURE`          | `TAVILY_MUX_COOKIE_SECURE`          | 通过 HTTPS 对外提供服务时应设置为 `true`                           |
| `DATABASE_URL`           | `TAVILY_MUX_DATABASE_URL`           | 默认使用 `/data/database.db`，通常无需修改                         |
| `MAX_REQUEST_BODY_BYTES` | `TAVILY_MUX_MAX_REQUEST_BODY_BYTES` | Search 请求体大小上限                                              |
| `GLOBAL_MAX_CONCURRENCY` | `TAVILY_MUX_GLOBAL_MAX_CONCURRENCY` | 单实例允许的全局并发数                                             |

如果遗失管理密钥，可以生成新密钥并撤销已有登录会话：

```bash
# Docker 部署：
docker exec -it tavilymux tavily-mux reset-admin-secret
# Compose 部署：
docker compose run --rm app reset-admin-secret
```

## 本地开发

本地开发需要 Python 3.13、uv、Node.js 24 和 npm
依赖安装、前后端启动、测试和构建方式见[本地开发指南](docs/cn/development.md)

## 当前局限

- [ ] 支持除 Search 之外的 Tavily Extract、Crawl、Map 和 Research 接口
- [ ] 支持多个 Uvicorn Worker 或多副本部署；当前路由状态、并发控制和 Key 冷却状态保存在单实例内存中
- [ ] 支持 PostgreSQL 等外部持久化数据库
- [ ] ~~支持多管理员、角色权限和相互隔离的管理空间；当前服务使用单一管理密钥~~
- [ ] 提供账号池、配置和加密数据的一体化备份与恢复工具
- [ ] 提供 Prometheus 指标、OpenTelemetry Trace 和更完整的运行告警集成
- [ ] 内置 HTTPS 证书管理；当前应由 Nginx、Caddy、Traefik 或云端网关终止 TLS

## 许可证

TavilyMux 使用 [MIT License](LICENSE) 发布。
