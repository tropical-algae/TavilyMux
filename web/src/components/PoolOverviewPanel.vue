<script setup lang="ts">
import { computed } from "vue"

import { useI18n } from "../i18n"
import type { PaginatedLogs, Pool, TavilyKey, UsageSnapshot } from "../types/api"
import { formatDate, formatLatency, formatNumber } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import LoadingSkeleton from "./LoadingSkeleton.vue"
import SelectControl from "./SelectControl.vue"
import UsageTimeline from "./UsageTimeline.vue"

const { t } = useI18n()

const props = defineProps<{
  pool: Pool
  keys: TavilyKey[]
  logs: PaginatedLogs | null
  snapshots: UsageSnapshot[]
  selectedKeyId: string
  showUsageSkeleton: boolean
}>()

const emit = defineEmits<{
  "update:selectedKeyId": [value: string]
}>()

const keyOptions = computed(() => props.keys.map((key) => ({ value: key.id, label: key.name })))
</script>

<template>
  <section class="telemetry-rail telemetry-rail--compact">
    <div>
      <span>{{ t("pool.overview.availableKeys") }}</span
      ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
    </div>
    <div>
      <span>{{ t("pool.overview.highestQuota") }}</span
      ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
    </div>
    <div>
      <span>{{ t("pool.overview.routing") }}</span
      ><strong>{{
        pool.strategy === "random" ? t("form.routingRandom") : t("form.routingMaxRemaining")
      }}</strong>
    </div>
    <div>
      <span>{{ t("pool.overview.maxAttempts") }}</span
      ><strong>{{ t("pool.overview.maxAttemptsValue", { count: pool.max_attempts }) }}</strong>
    </div>
  </section>

  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>{{ t("pool.overview.timelineTitle") }}</h2>
        <p>{{ t("pool.overview.timelineDescription") }}</p>
      </div>
      <SelectControl
        v-if="keys.length"
        :model-value="selectedKeyId"
        :options="keyOptions"
        :aria-label="t('pool.overview.selectKey')"
        @update:model-value="emit('update:selectedKeyId', $event)"
      />
    </div>
    <LoadingSkeleton v-if="showUsageSkeleton" class="skeleton--embedded" :rows="3" />
    <UsageTimeline v-else :snapshots="snapshots" />
  </section>

  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>{{ t("pool.overview.recentTitle") }}</h2>
        <p>{{ t("pool.overview.recentDescription") }}</p>
      </div>
    </div>
    <EmptyState
      v-if="!logs?.items.length"
      :title="t('pool.overview.recentEmpty')"
      :description="t('pool.overview.recentEmptyDescription')"
    />
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("pool.overview.tableTime") }}</th>
            <th>{{ t("pool.overview.tableStatus") }}</th>
            <th>{{ t("pool.overview.tableAttempts") }}</th>
            <th>{{ t("pool.overview.tableLatency") }}</th>
            <th>{{ t("pool.overview.tableRequestId") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs.items" :key="log.id">
            <td>{{ formatDate(log.created_at) }}</td>
            <td>
              <span
                class="http-status"
                :class="{ 'http-status--error': !log.status_code || log.status_code >= 400 }"
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
