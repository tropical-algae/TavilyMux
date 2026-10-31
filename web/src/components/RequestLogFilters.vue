<script setup lang="ts">
import { X } from "lucide-vue-next"
import { computed } from "vue"

import { useI18n } from "../i18n"
import type { Pool, TavilyKey } from "../types/api"
import type { RequestLogFilterField, RequestLogFilters } from "../types/requestLogs"
import DateTimeControl from "./DateTimeControl.vue"
import SelectControl from "./SelectControl.vue"

const { t } = useI18n()

const props = defineProps<{
  filters: RequestLogFilters
  pools: Pool[]
  keys: TavilyKey[]
  open: boolean
}>()

const emit = defineEmits<{
  change: [field: RequestLogFilterField, value: string]
  close: []
  commit: []
}>()

const poolOptions = computed(() => [
  { value: "", label: t("logs.allPools") },
  ...props.pools.map((pool) => ({ value: pool.id, label: pool.name })),
])
const keyOptions = computed(() => [
  { value: "", label: t("logs.allKeys") },
  ...props.keys.map((key) => ({ value: key.id, label: key.name })),
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

function inputValue(event: Event): string {
  return (event.target as HTMLInputElement).value
}
</script>

<template>
  <form
    class="filter-bar"
    :class="{ 'filter-bar--open': open }"
    @submit.prevent="emit('commit')"
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
        @click="emit('close')"
      >
        <X :size="18" />
      </button>
    </div>
    <div class="filter-field">
      <span>{{ t("logs.pool") }}</span>
      <SelectControl
        :model-value="filters.pool_id"
        :options="poolOptions"
        :aria-label="t('logs.pool')"
        @update:model-value="emit('change', 'pool_id', $event)"
      />
    </div>
    <div class="filter-field">
      <span>{{ t("logs.key") }}</span>
      <SelectControl
        :model-value="filters.key_id"
        :options="keyOptions"
        :aria-label="t('logs.key')"
        :disabled="!filters.pool_id"
        @update:model-value="emit('change', 'key_id', $event)"
      />
    </div>
    <label>
      <span>{{ t("logs.statusCode") }}</span>
      <input
        :value="filters.status_code"
        inputmode="numeric"
        maxlength="3"
        :placeholder="t('logs.statusPlaceholder')"
        @input="emit('change', 'status_code', inputValue($event))"
        @keydown.enter.prevent="emit('commit')"
      />
    </label>
    <div class="filter-field">
      <span>{{ t("logs.result") }}</span>
      <SelectControl
        :model-value="filters.success"
        :options="resultOptions"
        :aria-label="t('logs.result')"
        @update:model-value="emit('change', 'success', $event)"
      />
    </div>
    <div class="filter-field">
      <span>{{ t("logs.retryFilter") }}</span>
      <SelectControl
        :model-value="filters.retried"
        :options="retryOptions"
        :aria-label="t('logs.retryFilter')"
        @update:model-value="emit('change', 'retried', $event)"
      />
    </div>
    <label>
      <span>{{ t("logs.requestId") }}</span>
      <input
        :value="filters.request_id"
        maxlength="200"
        :placeholder="t('logs.requestIdPlaceholder')"
        @input="emit('change', 'request_id', inputValue($event))"
        @keydown.enter.prevent="emit('commit')"
      />
    </label>
    <div class="filter-field">
      <span>{{ t("logs.startTime") }}</span>
      <DateTimeControl
        :model-value="filters.time_from"
        :aria-label="t('logs.startTime')"
        @update:model-value="emit('change', 'time_from', $event)"
      />
    </div>
    <div class="filter-field">
      <span>{{ t("logs.endTime") }}</span>
      <DateTimeControl
        :model-value="filters.time_to"
        :aria-label="t('logs.endTime')"
        @update:model-value="emit('change', 'time_to', $event)"
      />
    </div>
  </form>
</template>
