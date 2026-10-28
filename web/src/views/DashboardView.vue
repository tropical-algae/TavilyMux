<script setup lang="ts">
import { ArrowUpRight, CircleAlert, Gauge, Network, Radio, TimerReset } from "lucide-vue-next"
import { computed, onMounted, ref } from "vue"
import { RouterLink } from "vue-router"

import { api, errorMessage } from "../api/client"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import StatusBadge from "../components/StatusBadge.vue"
import type { Dashboard, PaginatedLogs, Pool } from "../types/api"
import { formatDate, formatLatency, formatNumber } from "../utils/format"

const dashboard = ref<Dashboard | null>(null)
const pools = ref<Pool[]>([])
const logs = ref<PaginatedLogs | null>(null)
const loading = ref(true)
const error = ref("")

const serviceState = computed(() => {
  if (!dashboard.value || dashboard.value.pool_count === 0) return "等待配置"
  if (dashboard.value.healthy_pool_count === dashboard.value.pool_count) return "全部池正常"
  if (dashboard.value.healthy_pool_count > 0) return "部分池降级"
  return "当前无可用池"
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    const [dashboardResponse, poolResponse, logResponse] = await Promise.all([
      api.get<Dashboard>("/dashboard"),
      api.get<Pool[]>("/pools"),
      api.get<PaginatedLogs>("/logs", { params: { page_size: 6 } }),
    ])
    dashboard.value = dashboardResponse.data
    pools.value = poolResponse.data
    logs.value = logResponse.data
  } catch (cause) {
    error.value = errorMessage(cause, "总览数据加载失败")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="view-stack">
    <PageHeader title="运行总览" description="观察路由容量、池健康和最近一次调用链。">
      <template #actions>
        <RouterLink class="button button--primary" to="/pools"
          >管理账号池 <ArrowUpRight :size="17"
        /></RouterLink>
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="loading" :rows="6" />
    <div v-else-if="error" class="inline-error" role="alert">
      <p>{{ error }}</p>
      <button class="button button--secondary" type="button" @click="load">重新加载</button>
    </div>
    <template v-else-if="dashboard">
      <section class="telemetry-rail" aria-label="核心运行指标">
        <div class="telemetry-rail__state">
          <span class="signal-beacon" aria-hidden="true"></span>
          <div>
            <span>服务状态</span><strong>{{ serviceState }}</strong>
          </div>
        </div>
        <div>
          <Network :size="18" aria-hidden="true" />
          <span>健康池</span>
          <strong>{{ dashboard.healthy_pool_count }} / {{ dashboard.pool_count }}</strong>
        </div>
        <div>
          <Gauge :size="18" aria-hidden="true" />
          <span>可用 Key</span>
          <strong>{{ dashboard.available_key_count }} / {{ dashboard.key_count }}</strong>
        </div>
        <div>
          <Radio :size="18" aria-hidden="true" />
          <span>今日请求</span>
          <strong>{{ formatNumber(dashboard.requests_today) }}</strong>
        </div>
        <div>
          <TimerReset :size="18" aria-hidden="true" />
          <span>平均耗时</span>
          <strong>{{ formatLatency(dashboard.average_latency_ms) }}</strong>
        </div>
      </section>

      <div class="dashboard-grid">
        <section class="panel panel--pools">
          <div class="section-heading">
            <div>
              <h2>账号池航线</h2>
              <p>按可用性快速定位需要处理的池。</p>
            </div>
            <RouterLink to="/pools">查看全部</RouterLink>
          </div>
          <EmptyState
            v-if="pools.length === 0"
            title="还没有账号池"
            description="创建第一个池并添加 Tavily Key 后，搜索路由就会在这里点亮。"
          >
            <RouterLink class="button button--primary" to="/pools">创建账号池</RouterLink>
          </EmptyState>
          <div v-else class="pool-lanes">
            <RouterLink
              v-for="pool in pools.slice(0, 5)"
              :key="pool.id"
              :to="`/pools/${pool.id}`"
              class="pool-lane"
            >
              <span
                class="pool-lane__line"
                :class="`pool-lane__line--${pool.status}`"
                aria-hidden="true"
              ></span>
              <div class="pool-lane__identity">
                <strong>{{ pool.name }}</strong
                ><span>{{ pool.strategy === "random" ? "随机可用" : "剩余额度优先" }}</span>
              </div>
              <StatusBadge :status="pool.status" />
              <div>
                <span>Key</span
                ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
              </div>
              <div>
                <span>最高单 Key 可用</span
                ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
              </div>
              <ArrowUpRight :size="17" aria-hidden="true" />
            </RouterLink>
          </div>
        </section>

        <section class="panel panel--success">
          <div class="section-heading">
            <div>
              <h2>今日成功率</h2>
              <p>仅统计已经持久化的请求结果。</p>
            </div>
          </div>
          <div class="success-gauge" :style="{ '--success': `${dashboard.success_rate}%` }">
            <div>
              <strong>{{
                dashboard.requests_today ? `${dashboard.success_rate.toFixed(1)}%` : "—"
              }}</strong
              ><span>{{ dashboard.successes_today }} 次成功</span>
            </div>
          </div>
          <p class="metric-footnote">
            失败切换会记录为同一次外部请求，可在请求日志中展开查看。
          </p>
          <div class="capacity-summary">
            <div>
              <span>最高可路由额度</span
              ><strong>{{ formatNumber(dashboard.estimated_remaining) }}</strong>
            </div>
            <div>
              <span>今日已知消耗</span
              ><strong>{{ formatNumber(dashboard.credits_today) }}</strong>
            </div>
          </div>
        </section>
      </div>

      <section v-if="dashboard.alerts.length" class="panel alert-panel">
        <div class="section-heading">
          <div>
            <h2>当前告警</h2>
            <p>由池可用性、Key 状态与日志队列实时汇总。</p>
          </div>
          <span class="alert-count">{{ dashboard.alerts.length }}</span>
        </div>
        <div class="alert-list">
          <component
            :is="alert.pool_id ? RouterLink : 'div'"
            v-for="alert in dashboard.alerts"
            :key="`${alert.code}-${alert.pool_id}-${alert.key_id}`"
            :to="alert.pool_id ? `/pools/${alert.pool_id}` : undefined"
            class="alert-record"
            :class="`alert-record--${alert.severity}`"
          >
            <CircleAlert :size="17" aria-hidden="true" />
            <span>{{ alert.message }}</span>
            <ArrowUpRight v-if="alert.pool_id" :size="15" aria-hidden="true" />
          </component>
        </div>
      </section>

      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>最近请求</h2>
            <p>从外部请求到内部尝试的完整关联。</p>
          </div>
          <RouterLink to="/logs">打开日志</RouterLink>
        </div>
        <EmptyState
          v-if="!logs?.items.length"
          title="还没有请求记录"
          description="使用任意池的中转 Key 调用 /search 后，记录会出现在这里。"
        />
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>请求 ID</th>
                <th>结果</th>
                <th>尝试</th>
                <th>总耗时</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs.items" :key="log.id">
                <td>{{ formatDate(log.created_at) }}</td>
                <td>
                  <code>{{ log.id.slice(0, 12) }}</code>
                </td>
                <td>
                  <span
                    class="http-status"
                    :class="{
                      'http-status--error': !log.status_code || log.status_code >= 400,
                    }"
                    >{{ log.status_code ?? "ERR" }}</span
                  >
                </td>
                <td>{{ log.attempt_count }}</td>
                <td>{{ formatLatency(log.latency_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
