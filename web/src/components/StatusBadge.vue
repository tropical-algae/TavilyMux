<script setup lang="ts">
import { computed } from "vue"

import { type MessageKey, useI18n } from "../i18n"

const props = defineProps<{ status: string }>()
const { t } = useI18n()

const labels: Record<string, MessageKey> = {
  normal: "status.normal",
  degraded: "status.degraded",
  unavailable: "status.unavailable",
  disabled: "status.disabled",
  unknown: "status.unknown",
  available: "status.available",
  low_quota: "status.low_quota",
  rate_limited: "status.rate_limited",
  exhausted: "status.exhausted",
  invalid: "status.invalid",
  check_failed: "status.check_failed",
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
    {{ labels[status] ? t(labels[status]) : status }}
  </span>
</template>
