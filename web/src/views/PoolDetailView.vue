<script setup lang="ts">
import {
  Activity,
  ArrowLeft,
  BookOpenText,
  KeyRound,
  Settings,
  ShieldCheck,
  Trash2,
} from "lucide-vue-next"
import { computed, onMounted, reactive, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { api, errorMessage } from "../api/client"
import BaseModal from "../components/BaseModal.vue"
import ConfirmModal from "../components/ConfirmModal.vue"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import PoolAccessPanel from "../components/PoolAccessPanel.vue"
import PoolKeysPanel from "../components/PoolKeysPanel.vue"
import RequestLogList from "../components/RequestLogList.vue"
import SelectControl from "../components/SelectControl.vue"
import StatusBadge from "../components/StatusBadge.vue"
import UiButton from "../components/UiButton.vue"
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
import { formatDate, formatLatency, formatNumber } from "../utils/format"

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
const deletePoolOpen = ref(false)
const addingKeys = ref(false)
const creatingRelay = ref(false)
const deletingPool = ref(false)
const renamingKey = ref<TavilyKey | null>(null)
const renameKeyName = ref("")
const savingKeyName = ref(false)
const destructiveTarget = ref<
  { kind: "key"; item: TavilyKey } | { kind: "relay"; item: RelayKey } | null
>(null)
const deletingTarget = ref(false)
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
const canAddKeys = computed(() =>
  keyMode.value === "single"
    ? Boolean(keyForm.name && keyForm.api_key)
    : Boolean(keyForm.bulk.trim()),
)
const destructiveCopy = computed(() => {
  const target = destructiveTarget.value
  if (!target) return null
  if (target.kind === "key") {
    return {
      title: "删除 Tavily Key",
      description: `确认删除“${target.item.name}”吗？`,
      warningTitle: "此操作无法撤销",
      warningDescription: "该 Key 将立即退出路由候选，相关历史请求记录仍会保留。",
      confirmLabel: "确认删除 Key",
    }
  }
  return {
    title: "吊销中转凭证",
    description: `确认吊销“${target.item.name}”吗？`,
    warningTitle: "调用权限将立即失效",
    warningDescription: "所有正在使用这枚凭证的调用方都将无法继续访问 /search。",
    confirmLabel: "确认吊销凭证",
  }
})

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
  addingKeys.value = true
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
  } finally {
    addingKeys.value = false
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

function openRenameKey(key: TavilyKey): void {
  renamingKey.value = key
  renameKeyName.value = key.name
}

async function saveKeyName(): Promise<void> {
  const key = renamingKey.value
  const name = renameKeyName.value.trim()
  if (!key || !name || name === key.name) {
    renamingKey.value = null
    return
  }
  savingKeyName.value = true
  try {
    const updated = await api.patch<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}`, {
      name,
    })
    Object.assign(key, updated.data)
    renamingKey.value = null
    toasts.show("Key 名称已更新", "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, "Key 改名失败"), "error")
  } finally {
    savingKeyName.value = false
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

function requestDeleteKey(key: TavilyKey): void {
  destructiveTarget.value = { kind: "key", item: key }
}

async function createRelay(): Promise<void> {
  creatingRelay.value = true
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
  } finally {
    creatingRelay.value = false
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

function requestDeleteRelay(relay: RelayKey): void {
  destructiveTarget.value = { kind: "relay", item: relay }
}

async function confirmTargetDeletion(): Promise<void> {
  const target = destructiveTarget.value
  if (!target) return
  deletingTarget.value = true
  try {
    if (target.kind === "key") {
      await api.delete(`/pools/${poolId.value}/keys/${target.item.id}`)
      keys.value = keys.value.filter((item) => item.id !== target.item.id)
      toasts.show("Key 已删除", "success")
    } else {
      await api.delete(`/pools/${poolId.value}/relay-keys/${target.item.id}`)
      relayKeys.value = relayKeys.value.filter((item) => item.id !== target.item.id)
      toasts.show("中转凭证已吊销", "success")
    }
    destructiveTarget.value = null
  } catch (cause) {
    toasts.show(
      errorMessage(cause, target.kind === "key" ? "Key 删除失败" : "中转凭证吊销失败"),
      "error",
    )
  } finally {
    deletingTarget.value = false
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
  if (!pool.value) return
  deletingPool.value = true
  try {
    await api.delete(`/pools/${poolId.value}`)
    deletePoolOpen.value = false
    toasts.show("账号池已删除", "success")
    await router.push("/")
  } catch (cause) {
    toasts.show(errorMessage(cause, "账号池删除失败"), "error")
  } finally {
    deletingPool.value = false
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
      <UiButton @click="load">重新加载</UiButton>
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

      <PoolKeysPanel
        v-else-if="activeTab === 'keys'"
        :pool-id="poolId"
        :keys="keys"
        :busy-key="busyKey"
        @add="keyFormOpen = true"
        @check="checkKey"
        @rename="openRenameKey"
        @toggle="toggleKey"
        @delete="requestDeleteKey"
      />

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
        <RequestLogList
          v-else
          :logs="logs.items"
          :expanded="expandedLogs"
          @toggle="toggleLog"
        />
      </template>

      <PoolAccessPanel
        v-else-if="activeTab === 'access'"
        :relay-keys="relayKeys"
        :one-time-relay="oneTimeRelay"
        @create="relayFormOpen = true"
        @copy="copyRelay"
        @dismiss-secret="oneTimeRelay = null"
        @toggle="toggleRelay"
        @delete="requestDeleteRelay"
      />

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
          <UiButton variant="danger" @click="deletePoolOpen = true">
            <Trash2 :size="16" />删除账号池
          </UiButton>
          <UiButton variant="primary" type="submit">保存池设置</UiButton>
        </div>
      </form>
    </template>

    <BaseModal
      :open="keyFormOpen"
      title="添加 Tavily Key"
      description="添加后会立即进入后台额度检测，并参与当前池的路由。"
      size="large"
      :dismissible="!addingKeys"
      @close="keyFormOpen = false"
    >
      <form id="add-key-form" class="form-panel" @submit.prevent="addKeys">
        <div class="segmented">
          <button
            type="button"
            :class="{ active: keyMode === 'single' }"
            @click="keyMode = 'single'"
          >
            单个添加
          </button>
          <button
            type="button"
            :class="{ active: keyMode === 'bulk' }"
            @click="keyMode = 'bulk'"
          >
            批量粘贴
          </button>
        </div>
        <div v-if="keyMode === 'single'" class="form-grid">
          <label class="field">
            <span>名称</span>
            <input v-model.trim="keyForm.name" required placeholder="例如：主账号" />
          </label>
          <label class="field">
            <span>Tavily API Key</span>
            <input
              v-model.trim="keyForm.api_key"
              type="password"
              required
              autocomplete="off"
              placeholder="tvly-…"
            />
          </label>
        </div>
        <label v-else class="field">
          <span>每行一个 Key，可使用“名称,Key”格式</span>
          <textarea
            v-model="keyForm.bulk"
            rows="7"
            required
            placeholder="主账号,tvly-…&#10;备用账号,tvly-…"
          />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="addingKeys" @click="keyFormOpen = false">
          取消
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="add-key-form"
          :disabled="addingKeys || !canAddKeys"
        >
          {{ addingKeys ? "正在添加…" : "添加并开始检测" }}
        </UiButton>
      </template>
    </BaseModal>

    <BaseModal
      :open="relayFormOpen"
      title="生成中转凭证"
      description="凭证完整值只显示一次，生成后请立即安全保存。"
      size="small"
      :dismissible="!creatingRelay"
      @close="relayFormOpen = false"
    >
      <form id="create-relay-form" class="form-panel" @submit.prevent="createRelay">
        <label class="field">
          <span>凭证名称</span>
          <input v-model.trim="relayName" required autofocus placeholder="例如：生产环境" />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="creatingRelay" @click="relayFormOpen = false">
          取消
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="create-relay-form"
          :disabled="creatingRelay || !relayName"
        >
          {{ creatingRelay ? "正在生成…" : "生成凭证" }}
        </UiButton>
      </template>
    </BaseModal>

    <BaseModal
      :open="Boolean(renamingKey)"
      title="修改 Key 名称"
      description="名称仅用于控制台识别，不会发送给 Tavily。"
      size="small"
      :dismissible="!savingKeyName"
      @close="renamingKey = null"
    >
      <form id="rename-key-form" class="form-panel" @submit.prevent="saveKeyName">
        <label class="field">
          <span>Key 名称</span>
          <input v-model.trim="renameKeyName" required autofocus maxlength="100" />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="savingKeyName" @click="renamingKey = null">
          取消
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="rename-key-form"
          :disabled="savingKeyName || !renameKeyName.trim()"
        >
          {{ savingKeyName ? "正在保存…" : "保存名称" }}
        </UiButton>
      </template>
    </BaseModal>

    <ConfirmModal
      :open="deletePoolOpen"
      title="删除账号池"
      :description="pool ? `确认删除“${pool.name}”吗？` : undefined"
      warning-title="此操作无法撤销"
      warning-description="池内 Tavily Key、额度快照和全部中转凭证都会一并删除。"
      confirm-label="确认删除账号池"
      :busy="deletingPool"
      @close="deletePoolOpen = false"
      @confirm="deletePool"
    />

    <ConfirmModal
      v-if="destructiveCopy"
      :open="Boolean(destructiveTarget)"
      :title="destructiveCopy.title"
      :description="destructiveCopy.description"
      :warning-title="destructiveCopy.warningTitle"
      :warning-description="destructiveCopy.warningDescription"
      :confirm-label="destructiveCopy.confirmLabel"
      :busy="deletingTarget"
      @close="destructiveTarget = null"
      @confirm="confirmTargetDeletion"
    />
  </div>
</template>
