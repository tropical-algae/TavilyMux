import { readFileSync, mkdirSync } from "node:fs"
import { extname, join } from "node:path"
import { chromium } from "playwright"

const root = new URL("../dist/", import.meta.url).pathname
const publicRoot = new URL("../public/", import.meta.url).pathname
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

const keys = [
  {
    id: "key-primary",
    name: "生产主 Key",
    masked_key: "tvly-••••••••••4f2a",
    enabled: true,
    status: "available",
    usage: 2180,
    usage_limit: null,
    key_remaining: null,
    account_plan_remaining: 7820,
    paygo_remaining: 0,
    account_remaining: 7820,
    estimated_remaining: 7820,
    quota_bottleneck: "account",
    account_plan: "Researcher",
    account_plan_usage: 2180,
    account_plan_limit: 10000,
    paygo_usage: 0,
    paygo_limit: 0,
    cooldown_until: null,
    last_checked_at: "2026-10-28T12:05:00Z",
    last_used_at: "2026-10-28T12:05:00Z",
    request_count: 846,
    success_count: 835,
    failure_count: 11,
    last_error: null,
    created_at: "2026-10-27T08:00:00Z",
  },
  {
    id: "key-backup",
    name: "生产备用",
    masked_key: "tvly-••••••••••91bc",
    enabled: true,
    status: "low_quota",
    usage: 9400,
    usage_limit: 10000,
    key_remaining: 600,
    account_plan_remaining: 7820,
    paygo_remaining: 0,
    account_remaining: 7820,
    estimated_remaining: 600,
    quota_bottleneck: "key",
    account_plan: "Researcher",
    account_plan_usage: 2180,
    account_plan_limit: 10000,
    paygo_usage: 0,
    paygo_limit: 0,
    cooldown_until: null,
    last_checked_at: "2026-10-28T12:04:00Z",
    last_used_at: "2026-10-28T11:58:00Z",
    request_count: 302,
    success_count: 293,
    failure_count: 9,
    last_error: null,
    created_at: "2026-10-27T09:00:00Z",
  },
]

const relayKeys = [
  {
    id: "relay-production",
    name: "生产环境",
    prefix: "tpool_prod_••••9x2k",
    enabled: true,
    created_at: "2026-10-27T08:00:00Z",
    last_used_at: "2026-10-28T12:05:00Z",
  },
]

const usage = Array.from({ length: 12 }, (_, index) => ({
  captured_at: `2026-10-28T${String(index + 1).padStart(2, "0")}:00:00Z`,
  usage: 1850 + index * 30,
  usage_limit: null,
  account_plan_usage: 1850 + index * 30,
  account_plan_limit: 10000,
  paygo_usage: 0,
  paygo_limit: 0,
  key_remaining: null,
  account_plan_remaining: 8150 - index * 30,
  paygo_remaining: 0,
  account_remaining: 8150 - index * 30,
  estimated_remaining: 8150 - index * 30,
  quota_bottleneck: "account",
  status: "available",
}))

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
      if (url.pathname === "/api/v1/settings") {
        return json(route, {
          upstream_base_url: "https://api.tavily.com",
          http_proxy: "http://host.docker.internal:7890",
          https_proxy: "http://host.docker.internal:7890",
          allow_direct_fallback: false,
          monitor_interval_seconds: 300,
          request_timeout_seconds: 60,
          max_attempts: 3,
          log_retention_days: 30,
        })
      }
      if (url.pathname === "/api/v1/pools/pool-primary/keys/key-primary/usage") {
        return json(route, usage)
      }
      if (url.pathname === "/api/v1/pools/pool-primary/keys") return json(route, keys)
      if (url.pathname === "/api/v1/pools/pool-primary/relay-keys") {
        return json(route, relayKeys)
      }
      if (url.pathname === "/api/v1/pools/pool-primary") return json(route, pools[0])
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
    if (["/tavily-mux.svg", "/tavily-mux-dark.svg"].includes(url.pathname)) {
      return route.fulfill({
        status: 200,
        contentType: "image/svg+xml",
        body: readFileSync(join(publicRoot, url.pathname.slice(1))),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: "text/html",
      body: readFileSync(join(root, "index.html")),
    })
  })
}

async function capture(browser, name, viewport, path, authenticated, interact = null) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1, locale: "zh-CN" })
  await page.addInitScript(() => localStorage.setItem("tavily-mux-locale", "zh-CN"))
  await installRoutes(page, authenticated)
  await page.goto(`http://app.local${path}`, { waitUntil: "networkidle" })
  if (interact) {
    await interact(page)
    await page.waitForTimeout(320)
  }
  await page.evaluate(() => document.fonts.ready)
  const audit = await page.evaluate(() => {
    const isVisible = (element) => {
      const style = window.getComputedStyle(element)
      const bounds = element.getBoundingClientRect()
      return style.visibility !== "hidden" && style.display !== "none" && bounds.width > 0
    }
    const hasName = (element) => {
      const labelledBy = element.getAttribute("aria-labelledby")
      const labelledByText = labelledBy
        ?.split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent ?? "")
        .join(" ")
      const explicitLabel = element.id
        ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)?.textContent
        : ""
      return Boolean(
        element.getAttribute("aria-label")?.trim() ||
        labelledByText?.trim() ||
        explicitLabel?.trim() ||
        element.closest("label")?.textContent?.trim() ||
        element.getAttribute("title")?.trim() ||
        element.textContent?.trim(),
      )
    }
    const unnamed = Array.from(
      document.querySelectorAll(
        'button, a[href], input:not([type="hidden"]), select, textarea',
      ),
    )
      .filter(isVisible)
      .filter((element) => !hasName(element))
      .map((element) => element.outerHTML.slice(0, 160))

    return {
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
      unnamed,
    }
  })
  if (audit.horizontalOverflow > 1) {
    throw new Error(`${name}: body overflows viewport by ${audit.horizontalOverflow}px`)
  }
  if (audit.unnamed.length > 0) {
    throw new Error(`${name}: unnamed controls: ${audit.unnamed.join(" | ")}`)
  }
  await page.screenshot({ path: join(output, `${name}.png`), fullPage: true })
  await page.close()
}

const browser = await chromium.launch({
  headless: true,
  chromiumSandbox: false,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
})
try {
  await capture(browser, "login-desktop", { width: 1440, height: 900 }, "/login", false)
  await capture(browser, "login-mobile", { width: 390, height: 844 }, "/login", false)
  await capture(browser, "dashboard-desktop", { width: 1440, height: 1000 }, "/", true)
  await capture(browser, "dashboard-tablet", { width: 1024, height: 900 }, "/", true)
  await capture(browser, "dashboard-mobile", { width: 390, height: 844 }, "/", true)
  await capture(
    browser,
    "dashboard-english-dark-desktop",
    { width: 1440, height: 1000 },
    "/",
    true,
    async (page) => {
      await page.getByRole("button", { name: "切换为 English" }).click()
      await page.getByRole("button", { name: "Choose appearance" }).click()
      await page.getByRole("menuitemradio", { name: "Dark" }).click()
    },
  )
  await capture(
    browser,
    "pool-detail-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
  )
  await capture(
    browser,
    "pool-detail-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
  )
  await capture(
    browser,
    "pool-keys-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    (page) => page.getByRole("tab", { name: "Tavily Keys" }).click(),
  )
  await capture(
    browser,
    "pool-keys-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
    (page) => page.getByRole("tab", { name: "Tavily Keys" }).click(),
  )
  await capture(
    browser,
    "pool-keys-right-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "Tavily Keys" }).click()
      await page.locator(".key-table-scroll").evaluate((element) => {
        element.scrollLeft = element.scrollWidth
      })
    },
  )
  await capture(
    browser,
    "pool-keys-right-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "Tavily Keys" }).click()
      await page.locator(".key-table-scroll").evaluate((element) => {
        element.scrollLeft = element.scrollWidth
      })
    },
  )
  await capture(
    browser,
    "pool-key-modal-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "Tavily Keys" }).click()
      await page.getByRole("button", { name: "添加 Key" }).click()
    },
  )
  await capture(
    browser,
    "pool-rename-key-modal-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "Tavily Keys" }).click()
      await page.getByRole("button", { name: "改名" }).first().click()
    },
  )
  await capture(
    browser,
    "pool-delete-key-modal-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "Tavily Keys" }).click()
      await page.getByRole("button", { name: "删除 生产主 Key" }).click()
    },
  )
  await capture(
    browser,
    "pool-access-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    (page) => page.getByRole("tab", { name: "中转凭证" }).click(),
  )
  await capture(
    browser,
    "pool-access-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
    (page) => page.getByRole("tab", { name: "中转凭证" }).click(),
  )
  await capture(
    browser,
    "pool-relay-modal-mobile",
    { width: 390, height: 844 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "中转凭证" }).click()
      await page.getByRole("button", { name: "生成凭证" }).click()
    },
  )
  await capture(
    browser,
    "pool-delete-modal-desktop",
    { width: 1440, height: 1000 },
    "/pools/pool-primary",
    true,
    async (page) => {
      await page.getByRole("tab", { name: "池设置" }).click()
      await page.getByRole("button", { name: "删除账号池" }).click()
    },
  )
  await capture(browser, "logs-desktop", { width: 1440, height: 1000 }, "/logs", true)
  await capture(
    browser,
    "logs-select-desktop",
    { width: 1440, height: 1000 },
    "/logs",
    true,
    (page) => page.getByRole("combobox").first().click(),
  )
  await capture(
    browser,
    "logs-date-modal-desktop",
    { width: 1440, height: 1000 },
    "/logs",
    true,
    (page) => page.getByRole("button", { name: "开始时间" }).click(),
  )
  await capture(browser, "logs-mobile", { width: 390, height: 844 }, "/logs", true)
  await capture(browser, "settings-desktop", { width: 1440, height: 1000 }, "/settings", true)
  await capture(browser, "settings-tablet", { width: 768, height: 1024 }, "/settings", true)
  await capture(browser, "settings-mobile", { width: 390, height: 844 }, "/settings", true)
  await capture(browser, "command-desktop", { width: 1440, height: 1000 }, "/", true, (page) =>
    page.keyboard.press("/"),
  )
  await capture(browser, "pool-create-mobile", { width: 390, height: 844 }, "/", true, (page) =>
    page.getByRole("button", { name: /创建账号池/ }).click(),
  )
  await capture(
    browser,
    "logs-filter-mobile",
    { width: 390, height: 844 },
    "/logs",
    true,
    (page) => page.getByRole("button", { name: "筛选", exact: true }).click(),
  )
  await capture(
    browser,
    "logs-date-modal-mobile",
    { width: 390, height: 844 },
    "/logs",
    true,
    async (page) => {
      await page.getByRole("button", { name: "筛选", exact: true }).click()
      await page.getByRole("button", { name: "开始时间" }).click()
    },
  )
} finally {
  await browser.close()
}

console.log(output)
