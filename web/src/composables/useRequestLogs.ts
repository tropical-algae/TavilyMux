import axios from "axios"
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { api, errorMessage } from "../api/client"
import { FILTER_TIMING } from "../config/experience"
import { useI18n } from "../i18n"
import type { PaginatedLogs, Pool, TavilyKey } from "../types/api"
import type { RequestLogFilterField, RequestLogFilters } from "../types/requestLogs"
import {
  countRequestLogFilters,
  createRequestLogFilters,
  parseRequestLogFilters,
  requestLogQueryMatches,
  serializeRequestLogFilters,
  toRequestLogApiParams,
} from "../utils/requestLogFilters"
import { useLoadingBoundary } from "./useLoadingBoundary"

const DEBOUNCED_FIELDS = new Set<RequestLogFilterField>(["status_code", "request_id"])

export function useRequestLogs() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useI18n()
  const { initialized, loading, run: runLoad, showSkeleton } = useLoadingBoundary()

  const logs = ref<PaginatedLogs | null>(null)
  const pools = ref<Pool[]>([])
  const keys = ref<TavilyKey[]>([])
  const filters = ref<RequestLogFilters>(createRequestLogFilters())
  const error = ref("")
  const activeFilterCount = computed(() => countRequestLogFilters(filters.value))

  const keyCache = new Map<string, TavilyKey[]>()
  let poolsLoaded = false
  let activeController: AbortController | null = null
  let requestVersion = 0
  let commitTimer: ReturnType<typeof setTimeout> | null = null

  function cancelCommitTimer(): void {
    if (commitTimer !== null) clearTimeout(commitTimer)
    commitTimer = null
  }

  async function fetchPools(signal: AbortSignal): Promise<Pool[]> {
    if (poolsLoaded) return pools.value
    return (await api.get<Pool[]>("/pools", { signal })).data
  }

  async function fetchKeys(poolId: string, signal: AbortSignal): Promise<TavilyKey[]> {
    if (!poolId) return []
    const cached = keyCache.get(poolId)
    if (cached) return cached
    return (await api.get<TavilyKey[]>(`/pools/${poolId}/keys`, { signal })).data
  }

  async function execute(query: RequestLogFilters): Promise<void> {
    const version = ++requestVersion
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    error.value = ""

    await runLoad(async () => {
      try {
        const [nextLogs, nextPools, nextKeys] = await Promise.all([
          api.get<PaginatedLogs>("/logs", {
            params: toRequestLogApiParams(query),
            signal: controller.signal,
          }),
          fetchPools(controller.signal),
          fetchKeys(query.pool_id, controller.signal),
        ])
        if (version !== requestVersion) return

        logs.value = nextLogs.data
        pools.value = nextPools
        poolsLoaded = true
        keys.value = nextKeys
        if (query.pool_id) keyCache.set(query.pool_id, nextKeys)
      } catch (cause) {
        if (axios.isCancel(cause) || version !== requestVersion) return
        error.value = errorMessage(cause, t("logs.loadError"))
      }
    })
  }

  function commitFilters(force = false): void {
    cancelCommitTimer()
    const nextQuery = serializeRequestLogFilters(filters.value)
    if (requestLogQueryMatches(route.query, filters.value)) {
      if (force) void execute(filters.value)
      return
    }
    void router.replace({ name: "logs", query: nextQuery })
  }

  function scheduleCommit(): void {
    cancelCommitTimer()
    commitTimer = setTimeout(() => commitFilters(), FILTER_TIMING.textInputDebounceMs)
  }

  function updateFilter(field: RequestLogFilterField, rawValue: string): void {
    let value = rawValue
    if (field === "status_code") value = value.replace(/\D/g, "").slice(0, 3)
    if (field === "request_id") value = value.slice(0, 200)

    const next = { ...filters.value, [field]: value, page: 1 }
    if (field === "pool_id") {
      next.key_id = ""
      keys.value = keyCache.get(value) ?? []
    }
    filters.value = next

    if (DEBOUNCED_FIELDS.has(field)) scheduleCommit()
    else commitFilters()
  }

  function resetFilters(): void {
    cancelCommitTimer()
    filters.value = createRequestLogFilters()
    keys.value = []
    commitFilters()
  }

  function setPage(page: number): void {
    filters.value = { ...filters.value, page: Math.max(1, page) }
    commitFilters()
  }

  function previousPage(): void {
    setPage(filters.value.page - 1)
  }

  function nextPage(): void {
    setPage(filters.value.page + 1)
  }

  function refresh(): void {
    void execute(parseRequestLogFilters(route.query))
  }

  watch(
    () => route.fullPath,
    () => {
      cancelCommitTimer()
      const nextFilters = parseRequestLogFilters(route.query)
      filters.value = nextFilters
      keys.value = nextFilters.pool_id ? (keyCache.get(nextFilters.pool_id) ?? []) : []

      if (!requestLogQueryMatches(route.query, nextFilters)) {
        void router.replace({ name: "logs", query: serializeRequestLogFilters(nextFilters) })
        return
      }
      void execute(nextFilters)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    cancelCommitTimer()
    activeController?.abort()
  })

  return {
    activeFilterCount,
    error,
    filters,
    initialized,
    keys,
    loading,
    logs,
    nextPage,
    pools,
    previousPage,
    refresh,
    resetFilters,
    showSkeleton,
    updateFilter,
    commitFilters: () => commitFilters(true),
  }
}
