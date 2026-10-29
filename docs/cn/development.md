# 本地开发指南

本文介绍 TavilyMux 的本地开发环境、启动方式和质量检查命令

## 环境要求

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 24
- npm

## 安装依赖

在项目根目录执行：

```bash
uv sync --frozen
npm --prefix web ci
```

后端依赖安装在项目的 `.venv` 中，前端依赖安装在 `web/node_modules`

如需指定开发配置，复制示例文件（取其一即可）：

```bash
cp .env.example .env
cp config.yaml.example config.yaml
```

环境变量的优先级高于 `.env` 和 `config.yaml`。本地生成的数据库、主密钥和运行数据默认保存在 `data/`

## 启动开发环境

**后端启动**：

```bash
uv run poe run
```

后端默认监听 `http://127.0.0.1:8080`。首次启动未配置 `TAVILY_MUX_ADMIN_SECRET` 时，终端日志会输出随机生成的管理密钥

**前端启动**：

```bash
npm --prefix web run dev
```

访问 `http://localhost:5173`。Vite 会将 `/api`、`/search`、`/livez` 和 `/readyz` 转发到本地后端

## 生产前端联调

构建前端并让 FastAPI 直接提供静态文件：

```bash
npm --prefix web run build
TAVILY_MUX_WEB_ROOT=web/dist uv run poe run
```

此时 Web 控制台和 API 共用 `http://localhost:8080`，行为与生产镜像一致

## 质量检查

运行全部后端检查、测试和前端构建：

```bash
uv run poe test-all
```

也可以单独执行：

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

提交前可运行完整的 pre-commit 检查：

```bash
uv run pre-commit run --all-files --show-diff-on-failure
```

## Docker 构建

在项目根目录构建生产镜像：

```bash
docker build -t tavilymux:local .
```
