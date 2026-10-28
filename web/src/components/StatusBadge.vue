<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{ status: string }>()

const labels: Record<string, string> = {
  normal: "正常",
  degraded: "降级",
  unavailable: "不可用",
  disabled: "已停用",
  unknown: "待检测",
  available: "可用",
  low_quota: "额度偏低",
  rate_limited: "临时限流",
  exhausted: "额度耗尽",
  invalid: "鉴权失败",
  check_failed: "检测失败",
}

const tone = computed(() => {
  if (["normal", "available"].includes(props.status)) return "positive"
  if (["degraded", "low_quota", "rate_limited", "unknown"].includes(props.status)) {
    return "warning"
  }
  if (["unavailable", "exhausted", "invalid", "check_failed"].includes(props.status)) {
    return "negative"
  }
  return "neutral"
})
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone}`">
    <span class="status-badge__dot" aria-hidden="true"></span>
    {{ labels[status] ?? status }}
  </span>
</template>
