<script setup lang="ts">
import { computed } from "vue"

import { useI18n } from "../i18n"
import { formatNumber } from "../utils/format"

const { t } = useI18n()

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
  if (props.usage === null && props.limit === null) return t("common.notSynced")
  return `${formatNumber(props.usage)} / ${
    props.limit === null ? t("common.unlimited") : formatNumber(props.limit)
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
      :aria-label="t('common.usageLabel', { label })"
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
