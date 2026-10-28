<script setup lang="ts">
import { computed } from "vue"

import type { UsageSnapshot } from "../types/api"
import { formatDate, formatNumber } from "../utils/format"
import {
  buildTimelineScale,
  sampleTimelineIndexes,
  scaleTimelineValue,
} from "../utils/timeline"

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
  if (usage === null && limit === null) return "尚未同步"
  const used = formatNumber(usage)
  return `${used} / ${limit === null && unlimited ? "未设上限" : formatNumber(limit)}`
}

function bottleneckLabel(value: UsageSnapshot["quota_bottleneck"] | undefined): string {
  return {
    key: "Key 独立限额",
    account: "账户额度",
    both: "Key 与账户同时",
    unknown: "尚未确定",
  }[value ?? "unknown"]
}

const showPaygo = computed(
  () =>
    last.value !== null &&
    (last.value.paygo_limit !== null || (last.value.paygo_usage ?? 0) > 0),
)

const timelineDateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

function formatTimelineDate(value: string | null): string {
  return value ? timelineDateFormatter.format(new Date(value)).replace(" ", "\u00a0") : "—"
}
</script>

<template>
  <div v-if="snapshots.length" class="usage-timeline">
    <div class="usage-timeline__summary">
      <div>
        <span>实际可用额度</span
        ><strong>{{ formatNumber(last?.estimated_remaining ?? null) }}</strong
        ><small>瓶颈：{{ bottleneckLabel(last?.quota_bottleneck) }}</small>
      </div>
      <div>
        <span>Key 用量 / 独立上限</span
        ><strong>{{ quotaPair(last?.usage ?? null, last?.usage_limit ?? null, true) }}</strong>
      </div>
      <div>
        <span>账户套餐用量 / 上限</span
        ><strong>{{
          quotaPair(last?.account_plan_usage ?? null, last?.account_plan_limit ?? null)
        }}</strong>
      </div>
      <div v-if="showPaygo">
        <span>PAYGO 用量 / 上限</span
        ><strong>{{ quotaPair(last?.paygo_usage ?? null, last?.paygo_limit ?? null) }}</strong>
      </div>
      <div>
        <span>最后检测</span><strong>{{ formatDate(last?.captured_at ?? null) }}</strong>
      </div>
    </div>
    <div
      v-if="points"
      class="usage-chart"
      role="img"
      :aria-label="`实际可用额度从 ${formatNumber(scale?.maximum ?? null)} 到 ${formatNumber(scale?.minimum ?? null)} 的时间线`"
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
      <span class="usage-chart__axis-title usage-chart__axis-title--y">剩余额度</span>
      <span class="usage-chart__axis-title usage-chart__axis-title--x">检测时间</span>
    </div>
    <p v-else class="usage-timeline__unknown">当前快照不足以计算实际可用额度。</p>
  </div>
  <div v-else class="chart-empty">
    <p>还没有额度快照</p>
    <span>立即检测任意 Tavily Key 后，时间线会显示在这里。</span>
  </div>
</template>
