<script setup lang="ts">
import { RefreshCw, SlidersHorizontal } from "lucide-vue-next"
import { ref } from "vue"

import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import RequestLogFilters from "../components/RequestLogFilters.vue"
import RequestLogList from "../components/RequestLogList.vue"
import UiButton from "../components/UiButton.vue"
import { useRequestLogs } from "../composables/useRequestLogs"
import { useI18n } from "../i18n"

const { t } = useI18n()
const expanded = ref(new Set<string>())
const filtersOpen = ref(false)
const {
  activeFilterCount,
  commitFilters,
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
} = useRequestLogs()

function toggle(logId: string): void {
  const next = new Set(expanded.value)
  if (next.has(logId)) next.delete(logId)
  else next.add(logId)
  expanded.value = next
}
</script>

<template>
  <div class="view-stack">
    <PageHeader :title="t('logs.title')" :description="t('logs.description')">
      <template #actions>
        <UiButton class="filter-toggle" @click="filtersOpen = true">
          <SlidersHorizontal :size="16" />{{ t("logs.filter") }}
          <span v-if="activeFilterCount" class="filter-count">{{ activeFilterCount }}</span>
        </UiButton>
        <UiButton variant="ghost" :disabled="!activeFilterCount" @click="resetFilters">
          {{ t("common.reset") }}
        </UiButton>
        <UiButton :disabled="loading" @click="refresh">
          <RefreshCw :size="16" :class="{ spin: loading }" />{{ t("common.refresh") }}
        </UiButton>
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <template v-else-if="initialized">
      <RequestLogFilters
        :filters="filters"
        :pools="pools"
        :keys="keys"
        :open="filtersOpen"
        @change="updateFilter"
        @close="filtersOpen = false"
        @commit="commitFilters"
      />

      <div v-if="error" class="inline-error">
        <p>{{ error }}</p>
        <UiButton @click="refresh">{{ t("common.retry") }}</UiButton>
      </div>
      <EmptyState
        v-else-if="!logs?.items.length"
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
