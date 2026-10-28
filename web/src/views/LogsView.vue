<script setup lang="ts">
import { ChevronDown, ChevronRight, RefreshCw, SlidersHorizontal, X } from "lucide-vue-next"
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { api, errorMessage } from "../api/client"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import { useDelayedSkeleton } from "../composables/useDelayedSkeleton"
import type { PaginatedLogs, Pool, ProxyLog, TavilyKey } from "../types/api"
import { formatDate, formatLatency } from "../utils/format"

const logs = ref<PaginatedLogs | null>(null)
const pools = ref<Pool[]>([])
const keys = ref<TavilyKey[]>([])
const loading = ref(true)
const showSkeleton = useDelayedSkeleton(loading)
const error = ref("")
const expanded = ref(new Set<string>())
const filtersOpen = ref(false)
const route = useRoute()
const filters = ref({
  pool_id: typeof route.query.pool_id === "string" ? route.query.pool_id : "",
  key_id: typeof route.query.key_id === "string" ? route.query.key_id : "",
  status_code: "",
  success: "",
  retried: "",
  request_id: "",
  time_from: "",
  time_to: "",
  page: 1,
  page_size: 50,
})

const activeFilterCount = computed(
  () =>
    [
      filters.value.pool_id,
      filters.value.key_id,
      filters.value.status_code,
      filters.value.success,
      filters.value.retried,
      filters.value.request_id,
      filters.value.time_from,
      filters.value.time_to,
    ].filter(Boolean).length,
)

async function loadKeys(selectedKeyId = ""): Promise<void> {
  filters.value.key_id = ""
  if (!filters.value.pool_id) {
    keys.value = []
    return
  }
  try {
    keys.value = (await api.get<TavilyKey[]>(`/pools/${filters.value.pool_id}/keys`)).data
    if (selectedKeyId && keys.value.some((key) => key.id === selectedKeyId)) {
      filters.value.key_id = selectedKeyId
    }
  } catch {
    keys.value = []
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    const params = {
      page: filters.value.page,
      page_size: filters.value.page_size,
      pool_id: filters.value.pool_id || undefined,
      key_id: filters.value.key_id || undefined,
      status_code: filters.value.status_code || undefined,
      success: filters.value.success || undefined,
      retried: filters.value.retried || undefined,
      request_id: filters.value.request_id || undefined,
      time_from: filters.value.time_from
        ? new Date(filters.value.time_from).toISOString()
        : undefined,
      time_to: filters.value.time_to
        ? new Date(filters.value.time_to).toISOString()
        : undefined,
    }
    const [logResponse, poolResponse] = await Promise.all([
      api.get<PaginatedLogs>("/logs", { params }),
      pools.value.length ? Promise.resolve({ data: pools.value }) : api.get<Pool[]>("/pools"),
    ])
    logs.value = logResponse.data
    pools.value = poolResponse.data
  } catch (cause) {
    error.value = errorMessage(cause, "请求日志加载失败")
  } finally {
    loading.value = false
  }
}

function toggle(log: ProxyLog): void {
  const next = new Set(expanded.value)
  if (next.has(log.id)) next.delete(log.id)
  else next.add(log.id)
  expanded.value = next
}

function applyFilters(): void {
  filters.value.page = 1
  filtersOpen.value = false
  void load()
}

function clearFilters(): void {
  Object.assign(filters.value, {
    pool_id: "",
    key_id: "",
    status_code: "",
    success: "",
    retried: "",
    request_id: "",
    time_from: "",
    time_to: "",
    page: 1,
  })
  keys.value = []
  filtersOpen.value = false
  void load()
}

function previousPage(): void {
  filters.value.page -= 1
  void load()
}

function nextPage(): void {
  filters.value.page += 1
  void load()
}

onMounted(async () => {
  await loadKeys(typeof route.query.key_id === "string" ? route.query.key_id : "")
  await load()
})
</script>

<template>
  <div class="view-stack">
    <PageHeader
      title="请求日志"
      description="每条外部调用关联其内部 Key 尝试，不保存搜索正文。"
    >
      <template #actions>
        <button
          class="button button--quiet filter-toggle"
          type="button"
          @click="filtersOpen = true"
        >
          <SlidersHorizontal :size="16" />筛选
          <span v-if="activeFilterCount" class="filter-count">{{ activeFilterCount }}</span>
        </button>
        <button
          class="button button--secondary"
          type="button"
          :disabled="loading"
          @click="load"
        >
          <RefreshCw :size="16" :class="{ spin: loading }" />刷新
        </button>
      </template>
    </PageHeader>

    <form
      class="filter-bar"
      :class="{ 'filter-bar--open': filtersOpen }"
      @submit.prevent="applyFilters"
    >
      <div class="filter-bar__mobile-header">
        <div>
          <h2>筛选请求</h2>
          <p>组合条件快速定位一次调用链。</p>
        </div>
        <button
          class="icon-button"
          type="button"
          aria-label="关闭筛选"
          @click="filtersOpen = false"
        >
          <X :size="18" />
        </button>
      </div>
      <label
        ><span>账号池</span
        ><select v-model="filters.pool_id" @change="loadKeys()">
          <option value="">全部账号池</option>
          <option v-for="pool in pools" :key="pool.id" :value="pool.id">{{ pool.name }}</option>
        </select></label
      >
      <label
        ><span>Tavily Key</span
        ><select v-model="filters.key_id" :disabled="!filters.pool_id">
          <option value="">全部 Key</option>
          <option v-for="key in keys" :key="key.id" :value="key.id">{{ key.name }}</option>
        </select></label
      >
      <label
        ><span>状态码</span
        ><input v-model="filters.status_code" inputmode="numeric" placeholder="例如 200 / 429"
      /></label>
      <label
        ><span>结果</span
        ><select v-model="filters.success">
          <option value="">全部结果</option>
          <option value="true">成功</option>
          <option value="false">失败</option>
        </select></label
      >
      <label
        ><span>自动切换</span
        ><select v-model="filters.retried">
          <option value="">全部请求</option>
          <option value="true">发生切换</option>
          <option value="false">未切换</option>
        </select></label
      >
      <label
        ><span>请求 ID</span
        ><input v-model.trim="filters.request_id" placeholder="内部或外部请求 ID"
      /></label>
      <label
        ><span>开始时间</span><input v-model="filters.time_from" type="datetime-local"
      /></label>
      <label
        ><span>结束时间</span><input v-model="filters.time_to" type="datetime-local"
      /></label>
      <div class="filter-actions">
        <button
          class="button button--ghost"
          type="button"
          :disabled="!activeFilterCount"
          @click="clearFilters"
        >
          重置
        </button>
        <button class="button button--primary" type="submit">应用筛选</button>
      </div>
    </form>

    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error" class="inline-error">
      <p>{{ error }}</p>
      <button class="button button--secondary" @click="load">重新加载</button>
    </div>
    <EmptyState
      v-else-if="!logs?.items.length"
      title="没有符合条件的请求"
      description="调整筛选条件，或先通过任意中转 Key 调用 /search。"
    />
    <section v-else class="log-stream">
      <article v-for="log in logs.items" :key="log.id" class="log-entry">
        <button
          class="log-entry__summary"
          type="button"
          :aria-expanded="expanded.has(log.id)"
          @click="toggle(log)"
        >
          <ChevronDown v-if="expanded.has(log.id)" :size="17" /><ChevronRight
            v-else
            :size="17"
          />
          <time>{{ formatDate(log.created_at) }}</time>
          <code>{{ log.id }}</code>
          <span
            class="http-status"
            :class="{ 'http-status--error': !log.status_code || log.status_code >= 400 }"
            >{{ log.status_code ?? "ERR" }}</span
          >
          <span>{{ log.attempt_count }} 次尝试</span>
          <strong>{{ formatLatency(log.latency_ms) }}</strong>
        </button>
        <div v-if="expanded.has(log.id)" class="attempt-trace">
          <div class="attempt-trace__meta">
            <span
              >最终 Key：<code>{{ log.final_key_id || "未选择" }}</code></span
            ><span
              >外部请求 ID：<code>{{ log.external_request_id || "未提供" }}</code></span
            >
          </div>
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
                <strong
                  >第 {{ attempt.attempt_no }} 次 ·
                  {{ attempt.status_code ?? "网络错误" }}</strong
                ><code>{{ attempt.key_id || "Key 已删除" }}</code>
              </div>
              <span>{{ attempt.error_type || "完成" }}</span>
              <time>{{ formatLatency(attempt.latency_ms) }}</time>
            </li>
          </ol>
        </div>
      </article>
      <footer class="pagination">
        <span>共 {{ logs.total }} 条</span>
        <div>
          <button class="button button--tiny" :disabled="logs.page <= 1" @click="previousPage">
            上一页</button
          ><span>第 {{ logs.page }} 页</span
          ><button
            class="button button--tiny"
            :disabled="logs.page * logs.page_size >= logs.total"
            @click="nextPage"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>
