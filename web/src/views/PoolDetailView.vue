<script setup lang="ts">
import {
  Activity,
  ArrowLeft,
  BookOpenText,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  KeyRound,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
  Trash2,
} from "lucide-vue-next"
import { computed, onMounted, reactive, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { api, errorMessage } from "../api/client"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import SelectControl from "../components/SelectControl.vue"
import StatusBadge from "../components/StatusBadge.vue"
import UsageTimeline from "../components/UsageTimeline.vue"
import { useLoadingBoundary } from "../composables/useLoadingBoundary"
import { useToastStore } from "../stores/toasts"
import type {
  CreatedRelayKey,
  PaginatedLogs,
  Pool,
  RelayKey,
  RoutingStrategy,
  TavilyKey,
  UsageSnapshot,
} from "../types/api"
import { formatDate, formatLatency, formatNumber, successRate } from "../utils/format"

type Tab = "overview" | "keys" | "logs" | "access" | "settings"

const route = useRoute()
const router = useRouter()
const poolId = computed(() => String(route.params.id))
const pool = ref<Pool | null>(null)
const keys = ref<TavilyKey[]>([])
const relayKeys = ref<RelayKey[]>([])
const logs = ref<PaginatedLogs | null>(null)
const snapshots = ref<UsageSnapshot[]>([])
const selectedKeyId = ref("")
const activeTab = ref<Tab>("overview")
const expandedLogs = ref(new Set<string>())
const { run: runLoad, showSkeleton } = useLoadingBoundary()
const { run: runUsageLoad, showSkeleton: showUsageSkeleton } = useLoadingBoundary({
  skeletonOnRefresh: true,
})
const busyKey = ref("")
const error = ref("")
const keyFormOpen = ref(false)
const relayFormOpen = ref(false)
const keyMode = ref<"single" | "bulk">("single")
const keyForm = reactive({ name: "", api_key: "", bulk: "" })
const relayName = ref("")
const oneTimeRelay = ref<CreatedRelayKey | null>(null)
const connectionOverride = ref(false)
const proxyTouched = reactive({ http: false, https: false })
const settingsForm = reactive({
  name: "",
  description: "",
  enabled: true,
  strategy: "max_remaining" as RoutingStrategy,
  monitor_interval_seconds: 300,
  max_attempts: 3,
  concurrency_limit: null as number | null,
  rpm_limit: null as number | null,
  upstream_base_url: "",
  http_proxy: "",
  https_proxy: "",
  allow_direct_fallback: false,
})
const toasts = useToastStore()
const hydratingUsage = ref(false)

const routingOptions = [
  { value: "max_remaining", label: "剩余额度优先" },
  { value: "random", label: "随机可用 Key" },
]
const keyOptions = computed(() => keys.value.map((key) => ({ value: key.id, label: key.name })))

const tabs: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "概览", icon: Activity },
  { id: "keys", label: "Tavily Keys", icon: KeyRound },
  { id: "logs", label: "请求日志", icon: BookOpenText },
  { id: "access", label: "中转凭证", icon: ShieldCheck },
  { id: "settings", label: "池设置", icon: Settings },
]

function syncSettings(): void {
  if (!pool.value) return
  Object.assign(settingsForm, {
    name: pool.value.name,
    description: pool.value.description ?? "",
    enabled: pool.value.enabled,
    strategy: pool.value.strategy,
    monitor_interval_seconds: pool.value.monitor_interval_seconds,
    max_attempts: pool.value.max_attempts,
    concurrency_limit: pool.value.concurrency_limit,
    rpm_limit: pool.value.rpm_limit,
    upstream_base_url: pool.value.upstream_base_url ?? "",
    http_proxy: "",
    https_proxy: "",
    allow_direct_fallback: pool.value.allow_direct_fallback ?? false,
  })
  connectionOverride.value = Boolean(
    pool.value.upstream_base_url ||
    pool.value.http_proxy ||
    pool.value.https_proxy ||
    pool.value.allow_direct_fallback !== null,
  )
  proxyTouched.http = false
  proxyTouched.https = false
}

function quotaLabel(usage: number | null, limit: number | null): string {
  if (usage === null && limit === null) return "尚未同步"
  return `${formatNumber(usage)} / ${limit === null ? "未设上限" : formatNumber(limit)}`
}

function quotaPercent(usage: number | null, limit: number | null): number {
  if (usage === null || limit === null || limit <= 0) return 0
  return Math.min(100, Math.max(0, (usage / limit) * 100))
}

function quotaTone(usage: number | null, limit: number | null): string {
  const percent = quotaPercent(usage, limit)
  if (percent >= 95) return "danger"
  if (percent >= 80) return "warning"
  return "normal"
}

async function load(): Promise<void> {
  await runLoad(async () => {
    try {
      const [poolResponse, keyResponse, relayResponse, logResponse] = await Promise.all([
        api.get<Pool>(`/pools/${poolId.value}`),
        api.get<TavilyKey[]>(`/pools/${poolId.value}/keys`),
        api.get<RelayKey[]>(`/pools/${poolId.value}/relay-keys`),
        api.get<PaginatedLogs>("/logs", {
          params: { pool_id: poolId.value, page_size: 8 },
        }),
      ])
      const selectedKey =
        keyResponse.data.find((key) => key.id === selectedKeyId.value) ?? keyResponse.data[0]
      const usage = selectedKey
        ? await api
            .get<UsageSnapshot[]>(`/pools/${poolId.value}/keys/${selectedKey.id}/usage`)
            .then((response) => response.data)
            .catch(() => [])
        : []

      pool.value = poolResponse.data
      keys.value = keyResponse.data
      relayKeys.value = relayResponse.data
      logs.value = logResponse.data
      hydratingUsage.value = true
      selectedKeyId.value = selectedKey?.id ?? ""
      snapshots.value = usage
      hydratingUsage.value = false
      syncSettings()
      error.value = ""
    } catch (cause) {
      error.value = errorMessage(cause, "账号池详情加载失败")
    }
  })
}

async function loadUsage(keyId: string): Promise<void> {
  await runUsageLoad(async () => {
    if (!keyId) {
      snapshots.value = []
      return
    }
    try {
      snapshots.value = (
        await api.get<UsageSnapshot[]>(`/pools/${poolId.value}/keys/${keyId}/usage`)
      ).data
    } catch {
      snapshots.value = []
    }
  })
}

async function addKeys(): Promise<void> {
  try {
    if (keyMode.value === "single") {
      const response = await api.post<TavilyKey>(`/pools/${poolId.value}/keys`, {
        name: keyForm.name,
        api_key: keyForm.api_key,
      })
      keys.value.push(response.data)
    } else {
      const parsed = keyForm.bulk
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line, index) => {
          const separator = line.indexOf(",")
          return separator > 0
            ? {
                name: line.slice(0, separator).trim(),
                api_key: line.slice(separator + 1).trim(),
              }
            : { name: `Key ${keys.value.length + index + 1}`, api_key: line }
        })
      const response = await api.post<TavilyKey[]>(`/pools/${poolId.value}/keys/bulk`, {
        keys: parsed,
      })
      keys.value.push(...response.data)
    }
    keyForm.name = ""
    keyForm.api_key = ""
    keyForm.bulk = ""
    keyFormOpen.value = false
    toasts.show("Tavily Key 已添加，后台将自动检测额度", "success")
    await load()
  } catch (cause) {
    toasts.show(errorMessage(cause, "Tavily Key 添加失败"), "error")
  }
}

async function checkKey(key: TavilyKey): Promise<void> {
  busyKey.value = key.id
  try {
    const checked = await api.post<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}/check`)
    const index = keys.value.findIndex((item) => item.id === key.id)
    if (index >= 0) keys.value[index] = checked.data
    if (selectedKeyId.value === key.id) await loadUsage(key.id)
    if (checked.data.status === "check_failed") {
      toasts.show("检测失败：" + (checked.data.last_error ?? "上游未返回有效额度"), "error")
    } else if (checked.data.status === "invalid") {
      toasts.show("检测完成：Tavily Key 鉴权失败", "error")
    } else if (checked.data.status === "exhausted") {
      toasts.show("检测完成：实际可用额度已耗尽", "info")
    } else if (checked.data.status === "rate_limited") {
      toasts.show("检测完成：Tavily 暂时限制了请求频率", "info")
    } else {
      toasts.show("额度与状态已同步", "success")
    }
  } catch (cause) {
    toasts.show(errorMessage(cause, "检测失败，请检查上游连接"), "error")
  } finally {
    busyKey.value = ""
  }
}

async function renameKey(key: TavilyKey): Promise<void> {
  const name = window.prompt("新的 Key 名称", key.name)?.trim()
  if (!name || name === key.name) return
  try {
    const updated = await api.patch<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}`, {
      name,
    })
    Object.assign(key, updated.data)
    toasts.show("Key 名称已更新", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "Key 改名失败"), "error")
  }
}

async function toggleKey(key: TavilyKey): Promise<void> {
  try {
    const updated = await api.patch<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}`, {
      enabled: !key.enabled,
    })
    Object.assign(key, updated.data)
    toasts.show(key.enabled ? "Key 已启用" : "Key 已停用", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "Key 状态更新失败"), "error")
  }
}

async function deleteKey(key: TavilyKey): Promise<void> {
  if (!window.confirm(`确定删除 ${key.name}？此操作无法撤销。`)) return
  try {
    await api.delete(`/pools/${poolId.value}/keys/${key.id}`)
    keys.value = keys.value.filter((item) => item.id !== key.id)
    toasts.show("Key 已删除", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "Key 删除失败"), "error")
  }
}

async function createRelay(): Promise<void> {
  try {
    const response = await api.post<CreatedRelayKey>(`/pools/${poolId.value}/relay-keys`, {
      name: relayName.value,
    })
    oneTimeRelay.value = response.data
    relayKeys.value.unshift(response.data)
    relayName.value = ""
    relayFormOpen.value = false
  } catch (cause) {
    toasts.show(errorMessage(cause, "中转 Key 生成失败"), "error")
  }
}

async function toggleRelay(relay: RelayKey): Promise<void> {
  try {
    const response = await api.patch<RelayKey>(
      `/pools/${poolId.value}/relay-keys/${relay.id}`,
      { enabled: !relay.enabled },
    )
    Object.assign(relay, response.data)
    toasts.show(relay.enabled ? "中转凭证已启用" : "中转凭证已停用", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "中转凭证状态更新失败"), "error")
  }
}

async function deleteRelay(relay: RelayKey): Promise<void> {
  if (!window.confirm(`确定吊销 ${relay.name}？使用它的调用方会立即失去访问权限。`)) return
  try {
    await api.delete(`/pools/${poolId.value}/relay-keys/${relay.id}`)
    relayKeys.value = relayKeys.value.filter((item) => item.id !== relay.id)
    toasts.show("中转凭证已吊销", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "中转凭证吊销失败"), "error")
  }
}

async function copyRelay(): Promise<void> {
  if (!oneTimeRelay.value) return
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable")
    await navigator.clipboard.writeText(oneTimeRelay.value.relay_key)
    toasts.show("中转 Key 已复制", "success")
  } catch {
    toasts.show("自动复制失败，请手动选择上方完整 Key", "error")
  }
}

async function saveSettings(): Promise<void> {
  const payload: Record<string, string | number | boolean | null> = {
    name: settingsForm.name,
    description: settingsForm.description || null,
    enabled: settingsForm.enabled,
    strategy: settingsForm.strategy,
    monitor_interval_seconds: settingsForm.monitor_interval_seconds,
    max_attempts: settingsForm.max_attempts,
    concurrency_limit: settingsForm.concurrency_limit,
    rpm_limit: settingsForm.rpm_limit,
  }
  if (!connectionOverride.value) {
    Object.assign(payload, {
      upstream_base_url: null,
      http_proxy: null,
      https_proxy: null,
      allow_direct_fallback: null,
    })
  } else {
    payload.upstream_base_url = settingsForm.upstream_base_url || null
    payload.allow_direct_fallback = settingsForm.allow_direct_fallback
    if (proxyTouched.http) payload.http_proxy = settingsForm.http_proxy || null
    if (proxyTouched.https) payload.https_proxy = settingsForm.https_proxy || null
  }
  try {
    pool.value = (await api.patch<Pool>(`/pools/${poolId.value}`, payload)).data
    syncSettings()
    toasts.show("池设置已保存并应用到新请求", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "池设置保存失败"), "error")
  }
}

async function deletePool(): Promise<void> {
  if (
    !pool.value ||
    !window.confirm(`确定删除账号池 ${pool.value.name}？其 Key 和凭证会一并删除。`)
  ) {
    return
  }
  try {
    await api.delete(`/pools/${poolId.value}`)
    toasts.show("账号池已删除", "success")
    await router.push("/")
  } catch (cause) {
    toasts.show(errorMessage(cause, "账号池删除失败"), "error")
  }
}

function clearPoolProxy(kind: "http" | "https"): void {
  settingsForm[`${kind}_proxy`] = ""
  proxyTouched[kind] = true
}

function toggleLog(logId: string): void {
  const next = new Set(expandedLogs.value)
  if (next.has(logId)) next.delete(logId)
  else next.add(logId)
  expandedLogs.value = next
}

watch(
  selectedKeyId,
  (value) => {
    if (!hydratingUsage.value) void loadUsage(value)
  },
  { flush: "sync" },
)
onMounted(load)
</script>

<template>
  <div class="view-stack pool-detail-view">
    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error" class="inline-error">
      <p>{{ error }}</p>
      <button class="button button--secondary" @click="load">重新加载</button>
    </div>
    <template v-else-if="pool">
      <RouterLink class="back-link" to="/"><ArrowLeft :size="16" />返回账号池</RouterLink>
      <PageHeader :title="pool.name" :description="pool.description || '这个池还没有描述。'">
        <template #actions><StatusBadge :status="pool.status" /></template>
      </PageHeader>

      <nav class="tabs" role="tablist" aria-label="账号池详情">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" :size="17" />{{ tab.label }}
        </button>
      </nav>

      <template v-if="activeTab === 'overview'">
        <section class="telemetry-rail telemetry-rail--compact">
          <div>
            <span>可用 Key</span
            ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
          </div>
          <div>
            <span>最高单 Key 可用额度</span
            ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
          </div>
          <div>
            <span>路由策略</span
            ><strong>{{ pool.strategy === "random" ? "随机可用" : "剩余额度优先" }}</strong>
          </div>
          <div>
            <span>最大尝试</span><strong>{{ pool.max_attempts }} 次</strong>
          </div>
        </section>
        <section class="panel">
          <div class="section-heading">
            <div>
              <h2>额度时间线</h2>
              <p>同时核对 Key 独立限额与账户额度，实际可用值用于路由排序。</p>
            </div>
            <SelectControl
              v-if="keys.length"
              v-model="selectedKeyId"
              :options="keyOptions"
              aria-label="选择 Tavily Key"
            />
          </div>
          <LoadingSkeleton v-if="showUsageSkeleton" class="skeleton--embedded" :rows="3" />
          <UsageTimeline v-else :snapshots="snapshots" />
        </section>
        <section class="panel">
          <div class="section-heading">
            <div>
              <h2>最近请求</h2>
              <p>自动切换会以多次内部尝试呈现。</p>
            </div>
          </div>
          <EmptyState
            v-if="!logs?.items.length"
            title="这个池还没有请求"
            description="使用中转 Key 调用 /search 后即可观察路由结果。"
          />
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>状态</th>
                  <th>尝试</th>
                  <th>耗时</th>
                  <th>请求 ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in logs.items" :key="log.id">
                  <td>{{ formatDate(log.created_at) }}</td>
                  <td>
                    <span
                      class="http-status"
                      :class="{
                        'http-status--error': !log.status_code || log.status_code >= 400,
                      }"
                      >{{ log.status_code ?? "ERR" }}</span
                    >
                  </td>
                  <td>{{ log.attempt_count }}</td>
                  <td>{{ formatLatency(log.latency_ms) }}</td>
                  <td>
                    <code>{{ log.id.slice(0, 12) }}</code>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'keys'">
        <div class="section-actions">
          <div>
            <h2>Tavily Keys</h2>
            <p>真实 Key 只加密保存，页面始终脱敏显示。</p>
          </div>
          <button
            class="button button--primary"
            type="button"
            @click="keyFormOpen = !keyFormOpen"
          >
            <Plus :size="17" />添加 Key
          </button>
        </div>
        <form v-if="keyFormOpen" class="panel form-panel" @submit.prevent="addKeys">
          <div class="segmented">
            <button
              type="button"
              :class="{ active: keyMode === 'single' }"
              @click="keyMode = 'single'"
            >
              单个添加</button
            ><button
              type="button"
              :class="{ active: keyMode === 'bulk' }"
              @click="keyMode = 'bulk'"
            >
              批量粘贴
            </button>
          </div>
          <div v-if="keyMode === 'single'" class="form-grid">
            <label class="field"
              ><span>名称</span
              ><input v-model.trim="keyForm.name" required placeholder="例如：主账号" /></label
            ><label class="field"
              ><span>Tavily API Key</span
              ><input
                v-model.trim="keyForm.api_key"
                type="password"
                required
                autocomplete="off"
                placeholder="tvly-…"
            /></label>
          </div>
          <label v-else class="field"
            ><span>每行一个 Key，可使用“名称,Key”格式</span
            ><textarea
              v-model="keyForm.bulk"
              rows="7"
              required
              placeholder="主账号,tvly-…&#10;备用账号,tvly-…"
            />
          </label>
          <div class="form-actions">
            <button class="button button--primary" type="submit">添加并开始检测</button>
          </div>
        </form>
        <EmptyState
          v-if="keys.length === 0"
          title="池里还没有 Tavily Key"
          description="添加至少一个 Key 后，这个池才能接收搜索请求。"
        />
        <section v-else class="table-surface key-table-surface">
          <div class="table-wrap">
            <table class="key-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>API Key</th>
                  <th>状态</th>
                  <th>额度</th>
                  <th>成功率</th>
                  <th>最后检测</th>
                  <th class="align-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="key in keys" :key="key.id">
                  <td>
                    <strong class="key-name">{{ key.name }}</strong>
                  </td>
                  <td>
                    <code class="key-token" :title="key.masked_key">{{ key.masked_key }}</code>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <StatusBadge :status="key.status" />
                      <small v-if="key.last_error">{{ key.last_error }}</small>
                    </div>
                  </td>
                  <td>
                    <div class="quota-cell">
                      <strong class="quota-remaining">
                        剩余：{{ formatNumber(key.estimated_remaining) }}
                        <span>（{{ key.account_plan || "未知套餐" }}）</span>
                      </strong>
                      <div class="quota-meter">
                        <span>令牌额度</span>
                        <div
                          class="quota-progress"
                          :class="`quota-progress--${quotaTone(key.usage, key.usage_limit)}`"
                          role="progressbar"
                          aria-label="令牌额度使用量"
                          aria-valuemin="0"
                          :aria-valuemax="key.usage_limit ?? undefined"
                          :aria-valuenow="
                            key.usage_limit === null ? undefined : (key.usage ?? 0)
                          "
                          :aria-valuetext="quotaLabel(key.usage, key.usage_limit)"
                        >
                          <span
                            class="quota-progress__fill"
                            :style="{ width: `${quotaPercent(key.usage, key.usage_limit)}%` }"
                          ></span>
                          <strong>{{ quotaLabel(key.usage, key.usage_limit) }}</strong>
                        </div>
                      </div>
                      <div class="quota-meter">
                        <span>账户额度</span>
                        <div
                          class="quota-progress"
                          :class="`quota-progress--${quotaTone(key.account_plan_usage, key.account_plan_limit)}`"
                          role="progressbar"
                          aria-label="账户额度使用量"
                          aria-valuemin="0"
                          :aria-valuemax="key.account_plan_limit ?? undefined"
                          :aria-valuenow="
                            key.account_plan_limit === null
                              ? undefined
                              : (key.account_plan_usage ?? 0)
                          "
                          :aria-valuetext="
                            quotaLabel(key.account_plan_usage, key.account_plan_limit)
                          "
                        >
                          <span
                            class="quota-progress__fill"
                            :style="{
                              width: `${quotaPercent(key.account_plan_usage, key.account_plan_limit)}%`,
                            }"
                          ></span>
                          <strong>{{
                            quotaLabel(key.account_plan_usage, key.account_plan_limit)
                          }}</strong>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <strong>{{ successRate(key.success_count, key.request_count) }}</strong>
                      <small>{{ key.request_count }} 次请求</small>
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <strong>{{ formatDate(key.last_checked_at) }}</strong>
                      <small>最后使用：{{ formatDate(key.last_used_at) }}</small>
                    </div>
                  </td>
                  <td>
                    <div class="row-actions key-table__actions">
                      <button
                        class="icon-button"
                        type="button"
                        :disabled="busyKey === key.id"
                        :aria-label="`检测 ${key.name}`"
                        @click="checkKey(key)"
                      >
                        <RefreshCw :size="16" :class="{ spin: busyKey === key.id }" /></button
                      ><RouterLink
                        class="icon-button"
                        :to="`/logs?pool_id=${poolId}&key_id=${key.id}`"
                        :aria-label="`查看 ${key.name} 的日志`"
                      >
                        <BookOpenText :size="16" /> </RouterLink
                      ><button
                        class="button button--tiny"
                        type="button"
                        @click="renameKey(key)"
                      >
                        改名</button
                      ><button
                        class="button button--tiny"
                        type="button"
                        @click="toggleKey(key)"
                      >
                        {{ key.enabled ? "停用" : "启用" }}</button
                      ><button
                        class="icon-button icon-button--danger"
                        type="button"
                        :aria-label="`删除 ${key.name}`"
                        @click="deleteKey(key)"
                      >
                        <Trash2 :size="16" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'logs'">
        <div class="section-actions">
          <div>
            <h2>这个池的最近请求</h2>
            <p>展开可查看自动切换产生的每一次内部 Key 尝试。</p>
          </div>
          <RouterLink class="button button--secondary" :to="`/logs?pool_id=${poolId}`">
            查看与筛选全部日志
          </RouterLink>
        </div>
        <EmptyState
          v-if="!logs?.items.length"
          title="这个池还没有请求"
          description="使用中转 Key 调用 /search 后即可查看完整尝试链。"
        />
        <section v-else class="log-stream">
          <article v-for="log in logs.items" :key="log.id" class="log-entry">
            <button
              class="log-entry__summary"
              type="button"
              :aria-expanded="expandedLogs.has(log.id)"
              @click="toggleLog(log.id)"
            >
              <ChevronDown v-if="expandedLogs.has(log.id)" :size="17" />
              <ChevronRight v-else :size="17" />
              <time>{{ formatDate(log.created_at) }}</time>
              <code>{{ log.id }}</code>
              <span
                class="http-status"
                :class="{
                  'http-status--error': !log.status_code || log.status_code >= 400,
                }"
                >{{ log.status_code ?? "ERR" }}</span
              >
              <span>{{ log.attempt_count }} 次尝试</span>
              <strong>{{ formatLatency(log.latency_ms) }}</strong>
            </button>
            <div v-if="expandedLogs.has(log.id)" class="attempt-trace">
              <ol>
                <li v-for="attempt in log.attempts" :key="attempt.attempt_no">
                  <span
                    class="attempt-trace__node"
                    :class="{
                      'attempt-trace__node--error':
                        !attempt.status_code || attempt.status_code >= 400,
                    }"
                  ></span>
                  <div>
                    <strong>第 {{ attempt.attempt_no }} 次</strong>
                    <code>{{ attempt.key_id || "Key 已删除" }}</code>
                  </div>
                  <span>{{ attempt.error_type || "完成" }}</span>
                  <time>{{ formatLatency(attempt.latency_ms) }}</time>
                </li>
              </ol>
            </div>
          </article>
        </section>
      </template>

      <template v-else-if="activeTab === 'access'">
        <div class="section-actions">
          <div>
            <h2>中转凭证</h2>
            <p>调用方通过 Bearer 中转 Key 访问本服务的 /search。</p>
          </div>
          <button
            class="button button--primary"
            type="button"
            @click="relayFormOpen = !relayFormOpen"
          >
            <Plus :size="17" />生成凭证
          </button>
        </div>
        <section v-if="oneTimeRelay" class="one-time-secret">
          <div>
            <h2>新 Key 只显示这一次</h2>
            <p>复制后安全地交给调用方。</p>
          </div>
          <code>{{ oneTimeRelay.relay_key }}</code>
          <div class="one-time-secret__actions">
            <button class="button button--primary" type="button" @click="copyRelay">
              <Copy :size="16" />复制</button
            ><button class="button button--ghost" type="button" @click="oneTimeRelay = null">
              <CheckCircle2 :size="16" />我已保存
            </button>
          </div>
        </section>
        <form v-if="relayFormOpen" class="panel inline-form" @submit.prevent="createRelay">
          <label class="field"
            ><span>凭证名称</span
            ><input v-model.trim="relayName" required placeholder="例如：生产环境" /></label
          ><button class="button button--primary" type="submit" :disabled="!relayName">
            生成新的中转 Key
          </button>
        </form>
        <div class="credential-list">
          <article v-for="relay in relayKeys" :key="relay.id" class="credential-record">
            <div class="credential-record__identity">
              <span class="credential-record__icon"><KeyRound :size="18" /></span>
              <div>
                <strong>{{ relay.name }}</strong>
                <code>{{ relay.prefix }}_••••••••</code>
              </div>
            </div>
            <div class="credential-record__last-used">
              <span>最近使用</span>
              <strong>{{ formatDate(relay.last_used_at) }}</strong>
            </div>
            <StatusBadge :status="relay.enabled ? 'available' : 'disabled'" />
            <div class="row-actions">
              <button class="button button--tiny" type="button" @click="toggleRelay(relay)">
                {{ relay.enabled ? "停用" : "启用" }}</button
              ><button
                class="icon-button icon-button--danger"
                type="button"
                aria-label="吊销凭证"
                @click="deleteRelay(relay)"
              >
                <Trash2 :size="16" />
              </button>
            </div>
          </article>
        </div>
      </template>

      <form v-else class="panel settings-form" @submit.prevent="saveSettings">
        <div class="section-heading">
          <div>
            <h2>池级路由设置</h2>
            <p>保存后通过新的 Runtime 快照应用，不阻塞正在进行的请求。</p>
          </div>
        </div>
        <div class="form-grid">
          <label class="field"
            ><span>池名称</span><input v-model.trim="settingsForm.name" required
          /></label>
          <div class="field">
            <span>路由策略</span>
            <SelectControl v-model="settingsForm.strategy" :options="routingOptions" />
          </div>
          <label class="field field--span"
            ><span>描述</span><textarea v-model="settingsForm.description" rows="3" /></label
          ><label class="field"
            ><span>检测间隔（秒）</span
            ><input
              v-model.number="settingsForm.monitor_interval_seconds"
              type="number"
              min="60"
              max="86400" /></label
          ><label class="field"
            ><span>最大尝试次数</span
            ><input
              v-model.number="settingsForm.max_attempts"
              type="number"
              min="1"
              max="10" /></label
          ><label class="field"
            ><span>并发上限</span
            ><input
              v-model.number="settingsForm.concurrency_limit"
              type="number"
              min="1"
              placeholder="不限制" /></label
          ><label class="field"
            ><span>每分钟请求上限</span
            ><input
              v-model.number="settingsForm.rpm_limit"
              type="number"
              min="1"
              placeholder="不限制"
          /></label>
        </div>
        <label class="switch-field"
          ><input v-model="settingsForm.enabled" type="checkbox" /><span
            ><strong>启用账号池</strong><small>停用后所有中转凭证会立即停止路由。</small></span
          ></label
        >
        <div class="section-divider"></div>
        <div class="section-heading">
          <div>
            <h2>连接覆盖</h2>
            <p>默认继承全局 Tavily 地址和 Clash HTTP 代理；开启后仅影响这个池。</p>
          </div>
        </div>
        <label class="switch-field"
          ><input v-model="connectionOverride" type="checkbox" /><span
            ><strong>覆盖全局连接配置</strong
            ><small>关闭并保存会清除当前池的全部连接覆盖。</small></span
          ></label
        >
        <div v-if="connectionOverride" class="form-grid">
          <label class="field field--span"
            ><span>Tavily Base URL（留空继承全局）</span
            ><input
              v-model.trim="settingsForm.upstream_base_url"
              type="url"
              placeholder="https://api.tavily.com"
          /></label>
          <div class="field">
            <label for="pool-http-proxy">HTTP 代理</label>
            <input
              id="pool-http-proxy"
              v-model.trim="settingsForm.http_proxy"
              type="url"
              :placeholder="pool.http_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.http = true"
            /><small v-if="pool.http_proxy && !proxyTouched.http"
              >当前：{{ pool.http_proxy }}</small
            ><button
              v-if="pool.http_proxy"
              class="field-action"
              type="button"
              @click="clearPoolProxy('http')"
            >
              清除池级 HTTP 代理
            </button>
          </div>
          <div class="field">
            <label for="pool-https-proxy">HTTPS 代理</label>
            <input
              id="pool-https-proxy"
              v-model.trim="settingsForm.https_proxy"
              type="url"
              :placeholder="pool.https_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.https = true"
            /><small v-if="pool.https_proxy && !proxyTouched.https"
              >当前：{{ pool.https_proxy }}</small
            ><button
              v-if="pool.https_proxy"
              class="field-action"
              type="button"
              @click="clearPoolProxy('https')"
            >
              清除池级 HTTPS 代理
            </button>
          </div>
          <label class="switch-field field--span"
            ><input v-model="settingsForm.allow_direct_fallback" type="checkbox" /><span
              ><strong>代理失败时允许直连</strong
              ><small>可能使流量绕过代理，默认建议关闭。</small></span
            ></label
          >
        </div>
        <div class="form-actions">
          <button class="button button--primary" type="submit">保存池设置</button>
        </div>
        <div class="section-divider"></div>
        <div class="danger-zone">
          <div>
            <strong>删除账号池</strong>
            <p>同时删除池内的 Tavily Key、额度快照和所有中转凭证。</p>
          </div>
          <button class="button button--danger" type="button" @click="deletePool">
            <Trash2 :size="16" />删除账号池
          </button>
        </div>
      </form>
    </template>
  </div>
</template>
