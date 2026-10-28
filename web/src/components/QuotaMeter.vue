<script setup lang="ts">
import { computed } from "vue"

import { formatNumber } from "../utils/format"

const props = defineProps<{
  label: string
  usage: number | null
  limit: number | null
}>()

const percentage = computed(() => {
  if (props.usage === null || props.limit === null || props.limit <= 0) return 0
  return Math.min(100, Math.max(0, (props.usage / props.limit) * 100))
})

const valueLabel = computed(() => {
  if (props.usage === null && props.limit === null) return "尚未同步"
  return `${formatNumber(props.usage)} / ${
    props.limit === null ? "未设上限" : formatNumber(props.limit)
  }`
})

const tone = computed(() => {
  if (percentage.value >= 95) return "danger"
  if (percentage.value >= 80) return "warning"
  return "normal"
})
</script>

<template>
  <div class="quota-meter">
    <span>{{ label }}</span>
    <div
      class="quota-progress"
      :class="`quota-progress--${tone}`"
      role="progressbar"
      :aria-label="`${label}使用量`"
      aria-valuemin="0"
      :aria-valuemax="limit ?? undefined"
      :aria-valuenow="limit === null ? undefined : (usage ?? 0)"
      :aria-valuetext="valueLabel"
    >
      <span class="quota-progress__fill" :style="{ width: `${percentage}%` }"></span>
      <strong>{{ valueLabel }}</strong>
    </div>
  </div>
</template>
