<script setup lang="ts">
import { computed } from "vue"

import type { PaginatedLogs, Pool, TavilyKey, UsageSnapshot } from "../types/api"
import { formatDate, formatLatency, formatNumber } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import LoadingSkeleton from "./LoadingSkeleton.vue"
import SelectControl from "./SelectControl.vue"
import UsageTimeline from "./UsageTimeline.vue"

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
      <span>可用 Key</span
      ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
    </div>
    <div>
      <span>最高单 Key 可用额度</span
      ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
    </div>
    <div>
      <span>路由策略</span
      ><strong>{{ pool.strategy === "random" ? "随机可用" : "剩余额度优先" }}</strong>
    </div>
    <div>
      <span>最大尝试</span><strong>{{ pool.max_attempts }} 次</strong>
    </div>
  </section>

  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>额度时间线</h2>
        <p>同时核对 Key 独立限额与账户额度，实际可用值用于路由排序。</p>
      </div>
      <SelectControl
        v-if="keys.length"
        :model-value="selectedKeyId"
        :options="keyOptions"
        aria-label="选择 Tavily Key"
        @update:model-value="emit('update:selectedKeyId', $event)"
      />
    </div>
    <LoadingSkeleton v-if="showUsageSkeleton" class="skeleton--embedded" :rows="3" />
    <UsageTimeline v-else :snapshots="snapshots" />
  </section>

  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>最近请求</h2>
        <p>自动切换会以多次内部尝试呈现。</p>
      </div>
    </div>
    <EmptyState
      v-if="!logs?.items.length"
      title="这个池还没有请求"
      description="使用中转 Key 调用任一受支持接口后即可观察路由结果。"
    />
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>状态</th>
            <th>尝试</th>
            <th>耗时</th>
            <th>请求 ID</th>
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
