<script setup lang="ts">
import { computed } from "vue"

import type { UsageSnapshot } from "../types/api"
import { formatDate, formatNumber } from "../utils/format"

const props = defineProps<{ snapshots: UsageSnapshot[] }>()

const points = computed(() => {
  const values = props.snapshots
    .map((item) => item.estimated_remaining)
    .filter((value): value is number => value !== null)
  if (values.length === 0) return ""
  const maximum = Math.max(...values, 1)
  return values
    .map((value, index) => {
      const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100
      const y = 88 - (value / maximum) * 72
      return `${x},${y}`
    })
    .join(" ")
})

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
    <svg
      v-if="points"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      role="img"
      aria-label="实际可用额度时间线"
    >
      <line v-for="y in [16, 40, 64, 88]" :key="y" x1="0" :y1="y" x2="100" :y2="y" />
      <polyline :points="points" />
      <circle
        :cx="points.split(' ').at(-1)?.split(',')[0]"
        :cy="points.split(' ').at(-1)?.split(',')[1]"
        r="1.7"
      />
    </svg>
    <p v-else class="usage-timeline__unknown">当前快照不足以计算实际可用额度。</p>
  </div>
  <div v-else class="chart-empty">
    <p>还没有额度快照</p>
    <span>立即检测任意 Tavily Key 后，时间线会显示在这里。</span>
  </div>
</template>
