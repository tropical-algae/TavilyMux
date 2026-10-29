<script setup lang="ts">
import { RefreshCw, SlidersHorizontal, X } from "lucide-vue-next"
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { api, errorMessage } from "../api/client"
import DateTimeControl from "../components/DateTimeControl.vue"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import RequestLogList from "../components/RequestLogList.vue"
import SelectControl from "../components/SelectControl.vue"
import UiButton from "../components/UiButton.vue"
import { useLoadingBoundary } from "../composables/useLoadingBoundary"
import { useI18n } from "../i18n"
import type { PaginatedLogs, Pool, TavilyKey } from "../types/api"

const logs = ref<PaginatedLogs | null>(null)
const { t } = useI18n()
const pools = ref<Pool[]>([])
const keys = ref<TavilyKey[]>([])
const { initialized, loading, run: runLoad, showSkeleton } = useLoadingBoundary()
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

const poolOptions = computed(() => [
  { value: "", label: t("logs.allPools") },
  ...pools.value.map((pool) => ({ value: pool.id, label: pool.name })),
])
const keyOptions = computed(() => [
  { value: "", label: t("logs.allKeys") },
  ...keys.value.map((key) => ({ value: key.id, label: key.name })),
])
const resultOptions = computed(() => [
  { value: "", label: t("logs.allResults") },
  { value: "true", label: t("logs.success") },
  { value: "false", label: t("logs.failed") },
])
const retryOptions = computed(() => [
  { value: "", label: t("logs.allRequests") },
  { value: "true", label: t("logs.retried") },
  { value: "false", label: t("logs.noRetry") },
])

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

async function fetchLogs(): Promise<void> {
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
    time_to: filters.value.time_to ? new Date(filters.value.time_to).toISOString() : undefined,
  }
  const [logResponse, poolResponse] = await Promise.all([
    api.get<PaginatedLogs>("/logs", { params }),
    pools.value.length ? Promise.resolve({ data: pools.value }) : api.get<Pool[]>("/pools"),
  ])
  logs.value = logResponse.data
  pools.value = poolResponse.data
}

async function runDataLoad(operation: () => Promise<void>): Promise<void> {
  await runLoad(async () => {
    try {
      await operation()
      error.value = ""
    } catch (cause) {
      error.value = errorMessage(cause, t("logs.loadError"))
    }
  })
}

async function load(): Promise<void> {
  await runDataLoad(fetchLogs)
}

function toggle(logId: string): void {
  const next = new Set(expanded.value)
  if (next.has(logId)) next.delete(logId)
  else next.add(logId)
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

onMounted(() =>
  runDataLoad(async () => {
    await Promise.all([
      loadKeys(typeof route.query.key_id === "string" ? route.query.key_id : ""),
      fetchLogs(),
    ])
  }),
)
</script>

<template>
  <div class="view-stack">
    <PageHeader :title="t('logs.title')" :description="t('logs.description')">
      <template #actions>
        <UiButton class="filter-toggle" @click="filtersOpen = true">
          <SlidersHorizontal :size="16" />{{ t("logs.filter") }}
          <span v-if="activeFilterCount" class="filter-count">{{ activeFilterCount }}</span>
        </UiButton>
        <UiButton :disabled="loading" @click="load">
          <RefreshCw :size="16" :class="{ spin: loading }" />{{ t("common.refresh") }}
        </UiButton>
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error" class="inline-error">
      <p>{{ error }}</p>
      <UiButton @click="load">{{ t("common.retry") }}</UiButton>
    </div>
    <template v-else-if="initialized">
      <form
        class="filter-bar"
        :class="{ 'filter-bar--open': filtersOpen }"
        @submit.prevent="applyFilters"
      >
        <div class="filter-bar__mobile-header">
          <div>
            <h2>{{ t("logs.filterTitle") }}</h2>
            <p>{{ t("logs.filterDescription") }}</p>
          </div>
          <button
            class="icon-button"
            type="button"
            :aria-label="t('logs.closeFilters')"
            @click="filtersOpen = false"
          >
            <X :size="18" />
          </button>
        </div>
        <div class="filter-field">
          <span>{{ t("logs.pool") }}</span>
          <SelectControl
            v-model="filters.pool_id"
            :options="poolOptions"
            @change="loadKeys()"
          />
        </div>
        <div class="filter-field">
          <span>{{ t("logs.key") }}</span>
          <SelectControl
            v-model="filters.key_id"
            :options="keyOptions"
            :disabled="!filters.pool_id"
          />
        </div>
        <label>
          <span>{{ t("logs.statusCode") }}</span>
          <input
            v-model="filters.status_code"
            inputmode="numeric"
            :placeholder="t('logs.statusPlaceholder')"
          />
        </label>
        <div class="filter-field">
          <span>{{ t("logs.result") }}</span>
          <SelectControl v-model="filters.success" :options="resultOptions" />
        </div>
        <div class="filter-field">
          <span>{{ t("logs.retryFilter") }}</span>
          <SelectControl v-model="filters.retried" :options="retryOptions" />
        </div>
        <label>
          <span>{{ t("logs.requestId") }}</span>
          <input
            v-model.trim="filters.request_id"
            :placeholder="t('logs.requestIdPlaceholder')"
          />
        </label>
        <div class="filter-field">
          <span>{{ t("logs.startTime") }}</span>
          <DateTimeControl v-model="filters.time_from" :aria-label="t('logs.startTime')" />
        </div>
        <div class="filter-field">
          <span>{{ t("logs.endTime") }}</span>
          <DateTimeControl v-model="filters.time_to" :aria-label="t('logs.endTime')" />
        </div>
        <div class="filter-actions">
          <UiButton variant="ghost" :disabled="!activeFilterCount" @click="clearFilters">
            {{ t("common.reset") }}
          </UiButton>
          <UiButton variant="primary" type="submit">{{ t("logs.apply") }}</UiButton>
        </div>
      </form>

      <EmptyState
        v-if="!logs?.items.length"
        :title="t('logs.empty')"
        :description="t('logs.emptyDescription')"
      />
      <RequestLogList v-else :logs="logs.items" :expanded="expanded" @toggle="toggle">
        <template #footer>
          <footer class="pagination">
            <span>{{ t("logs.total", { count: logs.total }) }}</span>
            <div>
              <UiButton size="small" :disabled="logs.page <= 1" @click="previousPage">
                {{ t("logs.previous") }}</UiButton
              ><span>{{ t("logs.page", { page: logs.page }) }}</span
              ><UiButton
                size="small"
                :disabled="logs.page * logs.page_size >= logs.total"
                @click="nextPage"
              >
                {{ t("logs.next") }}
              </UiButton>
            </div>
          </footer>
        </template>
      </RequestLogList>
    </template>
  </div>
</template>
