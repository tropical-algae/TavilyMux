<script setup lang="ts">
import { ChevronDown, ChevronRight } from "lucide-vue-next"

import type { ProxyLog } from "../types/api"
import { formatDate, formatLatency } from "../utils/format"

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
        <span class="log-entry__attempts">{{ log.attempt_count }} 次尝试</span>
        <strong>{{ formatLatency(log.latency_ms) }}</strong>
      </button>
      <div v-if="expanded.has(log.id)" class="attempt-trace">
        <div class="attempt-trace__meta">
          <span
            >接口：<code>{{ log.endpoint }}</code></span
          >
          <span
            >最终 Key：<code>{{ log.final_key_id || "未选择" }}</code></span
          >
          <span
            >外部请求 ID：<code>{{ log.external_request_id || "未提供" }}</code></span
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
                第 {{ attempt.attempt_no }} 次 ·
                {{ attempt.status_code ?? "网络错误" }}
              </strong>
              <code>{{ attempt.key_id || "Key 已删除" }}</code>
            </div>
            <span>{{ attempt.error_type || "完成" }}</span>
            <time>{{ formatLatency(attempt.latency_ms) }}</time>
          </li>
        </ol>
      </div>
    </article>
    <slot name="footer" />
  </section>
</template>
