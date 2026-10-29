<script setup lang="ts">
import { ChevronDown, ChevronRight } from "lucide-vue-next"

import { useI18n } from "../i18n"
import type { ProxyLog } from "../types/api"
import { formatDate, formatLatency } from "../utils/format"

const { t } = useI18n()

defineProps<{
  logs: ProxyLog[]
  expanded: ReadonlySet<string>
}>()

defineEmits<{
  toggle: [logId: string]
}>()
</script>

<template>
  <section class="log-stream">
    <article v-for="log in logs" :key="log.id" class="log-entry">
      <button
        class="log-entry__summary"
        type="button"
        :aria-expanded="expanded.has(log.id)"
        @click="$emit('toggle', log.id)"
      >
        <ChevronDown v-if="expanded.has(log.id)" :size="17" />
        <ChevronRight v-else :size="17" />
        <time>{{ formatDate(log.created_at) }}</time>
        <span class="log-entry__endpoint">{{ log.method }} {{ log.path }}</span>
        <code>{{ log.id }}</code>
        <span
          class="http-status"
          :class="{ 'http-status--error': !log.status_code || log.status_code >= 400 }"
        >
          {{ log.status_code ?? "ERR" }}
        </span>
        <span class="log-entry__attempts">{{
          t("requestLog.attemptCount", { count: log.attempt_count })
        }}</span>
        <strong>{{ formatLatency(log.latency_ms) }}</strong>
      </button>
      <div v-if="expanded.has(log.id)" class="attempt-trace">
        <div class="attempt-trace__meta">
          <span
            >{{ t("requestLog.endpoint") }}<code>{{ log.endpoint }}</code></span
          >
          <span
            >{{ t("requestLog.finalKey")
            }}<code>{{ log.final_key_id || t("common.notSelected") }}</code></span
          >
          <span
            >{{ t("requestLog.externalId")
            }}<code>{{ log.external_request_id || t("common.notProvided") }}</code></span
          >
        </div>
        <ol>
          <li v-for="attempt in log.attempts" :key="attempt.attempt_no">
            <span
              class="attempt-trace__node"
              :class="{
                'attempt-trace__node--error':
                  !attempt.status_code || attempt.status_code >= 400,
              }"
            ></span>
            <div>
              <strong>
                {{
                  t("requestLog.attempt", {
                    count: attempt.attempt_no,
                    status: attempt.status_code ?? t("requestLog.networkError"),
                  })
                }}
              </strong>
              <code>{{ attempt.key_id || t("requestLog.keyDeleted") }}</code>
            </div>
            <span>{{ attempt.error_type || t("requestLog.completed") }}</span>
            <time>{{ formatLatency(attempt.latency_ms) }}</time>
          </li>
        </ol>
      </div>
    </article>
    <slot name="footer" />
  </section>
</template>
