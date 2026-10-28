# TavilyMux

[English](README.md)

一个可自托管的 Tavily API Key 池：提供透明、高并发的 `/search` 中转接口和 Web 管理控制台。

## 主要能力

- Tavily Search 无固定 Schema 转发：官方新增请求或响应字段无需重新发版。
- 在内存中按“剩余额度最多”或“随机可用”选择 Key，遇到额度、鉴权、限流或网络错误自动切换。
- 支持多个隔离账号池，以及可轮换、停用和吊销的中转 Key。
- Tavily Key 与代理凭据加密存储，管理密钥与中转 Key 只保存哈希或摘要。
- 定时查询 `/usage`，提供额度时间线、请求/内部尝试日志和当前告警。
- 支持全局及池级 Tavily 地址、Clash HTTP/HTTPS 代理配置。
- SQLite 持久化、后台异步批量落库、Docker、Nginx、CI 与语义化发布。

## Docker Compose 启动

```bash
docker compose up --build -d
docker compose logs app
```

访问 `http://localhost:8080`。首次使用新数据卷时，可以在 `.env` 配置 `TAVILY_MUX_ADMIN_SECRET`；未配置则自动生成高强度管理密钥，并仅在 app 首次初始化日志中完整显示一次。

数据库和自动生成的加密主密钥都保存在 `tavily-mux-data` 卷。备份时必须备份整个卷；缺少 `master.key` 时，`database.db` 中的敏感数据无法解密。

如果 Clash 运行在 Docker 宿主机，可填写 `http://host.docker.internal:7890`。Compose 已为 Linux 配置该主机名映射。

## 调用 Search 中转

在 Web 页面创建账号池、添加 Tavily Key，并保存只显示一次的中转 Key：

```bash
curl http://localhost:8080/search \
  -H 'Authorization: Bearer tpool_your_relay_key' \
  -H 'Content-Type: application/json' \
  -d '{"query":"Python 最新版本","search_depth":"advanced"}'
```

服务只解析中转鉴权并替换成选中的 Tavily Key；查询字符串、请求体、允许转发的请求头、状态码、响应头和响应流均尽可能原样传递。本地不定义 Tavily Search 的字段模型。

## 配置

启动配置支持环境变量、`.env` 和 YAML，优先级为：

```text
环境变量 > .env > config.yaml > 默认值
```

完整示例见 [.env.example](.env.example) 和 [config.yaml.example](config.yaml.example)。Tavily 地址、代理、监控间隔、请求超时、切换次数和日志保留时间可在 Web 页面动态修改。

管理密钥遗失时，可在部署环境重置；重置会同时使已有登录会话失效：

```bash
docker compose run --rm app reset-admin-secret
# 或：tavily-mux reset-admin-secret --secret '一个新的长管理密钥'
```

自动生成的值只显示一次。命令行直接传入密钥可能进入 Shell 历史，推荐让程序随机生成。

## 本地开发

需要 Python 3.13、`uv`、Node.js 24 和 npm。

```bash
uv sync --frozen
npm --prefix web ci
uv run poe test-all
uv run poe run
```

开发前端时另开终端执行 `npm --prefix web run dev`。生产构建使用 `npm --prefix web run build`；需要由 FastAPI 直接托管时设置 `TAVILY_MUX_WEB_ROOT=web/dist`。

常用检查命令：

```bash
uv run poe lint
uv run poe type-check
uv run poe test
npm --prefix web run lint
npm --prefix web run type-check
npm --prefix web run test
npm --prefix web run build
```

## 部署注意事项

- V0.1 明确采用单服务实例、单 Uvicorn Worker；多个 Worker 或副本之间无法共享内存路由和限流状态。
- Nginx 已关闭 `/search` 响应缓冲；如果关注流式延迟，不要在更外层重新开启缓冲。
- HTTPS 部署时设置 `TAVILY_MUX_COOKIE_SECURE=true`。
- 使用 Nginx 作为公开入口时，不要额外暴露 app 容器端口。
- 产品请求日志不保存 Tavily Key、中转 Key、代理密码或完整搜索正文。

## 许可证

[MIT](LICENSE)
