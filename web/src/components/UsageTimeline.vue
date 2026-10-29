<script setup lang="ts">
import { computed } from "vue"

import { currentLocale, useI18n } from "../i18n"
import type { UsageSnapshot } from "../types/api"
import { formatDate, formatNumber } from "../utils/format"
import {
  buildTimelineScale,
  sampleTimelineIndexes,
  scaleTimelineValue,
} from "../utils/timeline"

const { t } = useI18n()

const props = defineProps<{ snapshots: UsageSnapshot[] }>()

const chartWidth = 1000
const chartHeight = 240
const chartTop = 12
const chartBottom = 228

const plottedSnapshots = computed(() =>
  props.snapshots
    .map((snapshot, index) => ({ snapshot, index }))
    .filter(
      (
        entry,
      ): entry is {
        snapshot: UsageSnapshot & { estimated_remaining: number }
        index: number
      } => entry.snapshot.estimated_remaining !== null,
    ),
)

const scale = computed(() =>
  buildTimelineScale(
    plottedSnapshots.value.map(({ snapshot }) => snapshot.estimated_remaining),
  ),
)

function xPosition(index: number): number {
  return props.snapshots.length === 1
    ? chartWidth / 2
    : (index / (props.snapshots.length - 1)) * chartWidth
}

const points = computed(() => {
  if (!scale.value) return ""
  return plottedSnapshots.value
    .map(({ snapshot, index }) => {
      const x = xPosition(index)
      const y = scaleTimelineValue(
        snapshot.estimated_remaining,
        scale.value!,
        chartTop,
        chartBottom,
      )
      return `${x},${y}`
    })
    .join(" ")
})

const yTicks = computed(() =>
  (scale.value?.ticks ?? []).map((value) => ({
    value,
    position: scale.value
      ? scaleTimelineValue(value, scale.value, chartTop, chartBottom)
      : chartBottom,
  })),
)

const xTicks = computed(() =>
  sampleTimelineIndexes(props.snapshots.length).map((index) => ({
    index,
    position: xPosition(index),
    label: formatTimelineDate(props.snapshots[index]?.captured_at ?? null),
  })),
)

const last = computed(() => props.snapshots.at(-1) ?? null)

function quotaPair(usage: number | null, limit: number | null, unlimited = false): string {
  if (usage === null && limit === null) return t("common.notSynced")
  const used = formatNumber(usage)
  return `${used} / ${limit === null && unlimited ? t("common.unlimited") : formatNumber(limit)}`
}

const showPaygo = computed(
  () =>
    last.value !== null &&
    (last.value.paygo_limit !== null || (last.value.paygo_usage ?? 0) > 0),
)

function formatTimelineDate(value: string | null): string {
  if (!value) return "—"
  return new Intl.DateTimeFormat(currentLocale(), {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(new Date(value))
    .replace(" ", "\u00a0")
}
</script>

<template>
  <div v-if="snapshots.length" class="usage-timeline">
    <div class="usage-timeline__summary">
      <div>
        <span>{{ t("timeline.remaining") }}</span>
        <strong>{{ formatNumber(last?.estimated_remaining ?? null) }}</strong>
      </div>
      <div>
        <span>{{ t("timeline.token") }}</span
        ><strong>{{ quotaPair(last?.usage ?? null, last?.usage_limit ?? null, true) }}</strong>
      </div>
      <div>
        <span>{{ t("timeline.account") }}</span
        ><strong>{{
          quotaPair(last?.account_plan_usage ?? null, last?.account_plan_limit ?? null)
        }}</strong>
      </div>
      <div v-if="showPaygo">
        <span>{{ t("timeline.paygo") }}</span
        ><strong>{{ quotaPair(last?.paygo_usage ?? null, last?.paygo_limit ?? null) }}</strong>
      </div>
      <div>
        <span>{{ t("timeline.lastCheck") }}</span
        ><strong>{{ formatDate(last?.captured_at ?? null) }}</strong>
      </div>
    </div>
    <div
      v-if="points"
      class="usage-chart"
      role="img"
      :aria-label="
        t('timeline.aria', {
          maximum: formatNumber(scale?.maximum ?? null),
          minimum: formatNumber(scale?.minimum ?? null),
        })
      "
    >
      <div class="usage-chart__y-axis" aria-hidden="true">
        <span
          v-for="tick in yTicks"
          :key="tick.value"
          :style="{ top: `${(tick.position / chartHeight) * 100}%` }"
        >
          {{ formatNumber(tick.value) }}
        </span>
      </div>
      <div class="usage-chart__plot">
        <svg
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <line
            v-for="tick in yTicks"
            :key="`y-${tick.value}`"
            x1="0"
            :y1="tick.position"
            :x2="chartWidth"
            :y2="tick.position"
          />
          <line
            v-for="tick in xTicks"
            :key="`x-${tick.index}`"
            :x1="tick.position"
            :y1="chartTop"
            :x2="tick.position"
            :y2="chartBottom"
          />
          <polyline :points="points" />
        </svg>
      </div>
      <div aria-hidden="true"></div>
      <div class="usage-chart__x-axis" aria-hidden="true">
        <time
          v-for="(tick, index) in xTicks"
          :key="tick.index"
          :class="{
            'usage-chart__x-label--first': index === 0,
            'usage-chart__x-label--last': index === xTicks.length - 1,
          }"
          :style="{ left: `${(tick.position / chartWidth) * 100}%` }"
          :datetime="snapshots[tick.index]?.captured_at"
        >
          {{ tick.label }}
        </time>
      </div>
      <span class="usage-chart__axis-title usage-chart__axis-title--y">{{
        t("timeline.axisQuota")
      }}</span>
      <span class="usage-chart__axis-title usage-chart__axis-title--x">{{
        t("timeline.axisTime")
      }}</span>
    </div>
    <p v-else class="usage-timeline__unknown">{{ t("timeline.unknown") }}</p>
  </div>
  <div v-else class="chart-empty">
    <p>{{ t("timeline.empty") }}</p>
    <span>{{ t("timeline.emptyHint") }}</span>
  </div>
</template>
