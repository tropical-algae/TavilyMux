import { readFileSync, mkdirSync } from "node:fs"
import { extname, join } from "node:path"
import { chromium } from "playwright"

const root = new URL("../dist/", import.meta.url).pathname
const output = new URL("../../.artifacts/ui/", import.meta.url).pathname
mkdirSync(output, { recursive: true })

const pools = [
  {
    id: "pool-primary",
    name: "生产搜索",
    description: "面向生产 Agent 的主搜索池",
    enabled: true,
    status: "normal",
    strategy: "max_remaining",
    key_count: 4,
    available_key_count: 3,
    estimated_remaining: 7820,
    requests_today: 1032,
    success_rate_today: 98.2,
    last_used_at: "2026-10-28T12:05:00Z",
    monitor_interval_seconds: 300,
    max_attempts: 3,
    concurrency_limit: 200,
    rpm_limit: 1200,
    upstream_base_url: null,
    http_proxy: null,
    https_proxy: null,
    allow_direct_fallback: null,
    created_at: "2026-10-28T08:00:00Z",
    updated_at: "2026-10-28T12:00:00Z",
  },
  {
    id: "pool-research",
    name: "研究任务",
    description: "深度搜索与内部分析",
    enabled: true,
    status: "degraded",
    strategy: "random",
    key_count: 3,
    available_key_count: 1,
    estimated_remaining: 960,
    requests_today: 216,
    success_rate_today: 91.7,
    last_used_at: "2026-10-28T12:03:00Z",
    monitor_interval_seconds: 600,
    max_attempts: 3,
    concurrency_limit: 60,
    rpm_limit: null,
    upstream_base_url: null,
    http_proxy: null,
    https_proxy: null,
    allow_direct_fallback: null,
    created_at: "2026-10-27T08:00:00Z",
    updated_at: "2026-10-28T12:00:00Z",
  },
]

const logs = {
  total: 3,
  page: 1,
  page_size: 6,
  items: [200, 200, 429].map((status, index) => ({
    id: `3db13ba8-a81b-4ec5-b8d8-00000000000${index}`,
    pool_id: pools[index % 2].id,
    final_key_id: `key-${index}`,
    created_at: `2026-10-28T12:0${5 - index}:00Z`,
    completed_at: `2026-10-28T12:0${5 - index}:01Z`,
    status_code: status,
    latency_ms: 684 + index * 320,
    attempt_count: status === 429 ? 2 : 1,
    credits: null,
    error_type: status === 429 ? "rate_limited" : null,
    external_request_id: null,
    attempts: [],
  })),
}

function json(route, value, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(value),
  })
}

function contentType(pathname) {
  return {
    ".js": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
  }[extname(pathname)]
}

async function installRoutes(page, authenticated) {
  await page.route("http://app.local/**", async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.startsWith("/api/v1/")) {
      if (url.pathname === "/api/v1/auth/me") {
        return authenticated
          ? json(route, { authenticated: true })
          : json(route, { detail: "Authentication required" }, 401)
      }
      if (url.pathname === "/api/v1/dashboard") {
        return json(route, {
          pool_count: 2,
          healthy_pool_count: 1,
          normal_pool_count: 1,
          degraded_pool_count: 1,
          unavailable_pool_count: 0,
          disabled_pool_count: 0,
          key_count: 7,
          available_key_count: 4,
          estimated_remaining: 8780,
          requests_today: 1248,
          successes_today: 1216,
          credits_today: 1216,
          success_rate: 97.4,
          average_latency_ms: 812,
          dropped_log_events: 0,
          alerts: [
            {
              severity: "warning",
              code: "key_rate_limited",
              message: "Tavily Key“研究备用”正在被限流",
              pool_id: "pool-research",
              key_id: "key-2",
            },
          ],
        })
      }
      if (url.pathname === "/api/v1/pools") return json(route, pools)
      if (url.pathname === "/api/v1/logs") return json(route, logs)
      return json(route, {})
    }
    if (url.pathname.startsWith("/assets/")) {
      const path = join(root, url.pathname.slice(1))
      return route.fulfill({
        status: 200,
        contentType: contentType(path),
        body: readFileSync(path),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: "text/html",
      body: readFileSync(join(root, "index.html")),
    })
  })
}

async function capture(browser, name, viewport, path, authenticated) {
  const page = await browser.newPage({ viewportSize: viewport, deviceScaleFactor: 1 })
  await installRoutes(page, authenticated)
  await page.goto(`http://app.local${path}`, { waitUntil: "networkidle" })
  await page.screenshot({ path: join(output, `${name}.png`), fullPage: true })
  await page.close()
}

const browser = await chromium.launch({
  headless: true,
  chromiumSandbox: false,
  args: ["--no-zygote", "--single-process", "--disable-gpu"],
})
try {
  await capture(browser, "login-desktop", { width: 1440, height: 900 }, "/login", false)
  await capture(browser, "login-mobile", { width: 390, height: 844 }, "/login", false)
  await capture(browser, "dashboard-desktop", { width: 1440, height: 1000 }, "/", true)
  await capture(browser, "dashboard-mobile", { width: 390, height: 844 }, "/", true)
} finally {
  await browser.close()
}

console.log(output)
