<script setup lang="ts">
import { ArrowUpRight, CircleAlert, RefreshCw } from "lucide-vue-next"
import { computed, onMounted, ref } from "vue"
import { RouterLink } from "vue-router"

import { api, errorMessage } from "../api/client"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import RoutingMap from "../components/RoutingMap.vue"
import StatusBadge from "../components/StatusBadge.vue"
import type { Dashboard, PaginatedLogs, Pool } from "../types/api"
import { formatDate, formatLatency, formatNumber } from "../utils/format"

const dashboard = ref<Dashboard | null>(null)
const pools = ref<Pool[]>([])
const logs = ref<PaginatedLogs | null>(null)
const loading = ref(true)
const error = ref("")

const serviceState = computed(() => {
  if (!dashboard.value || dashboard.value.pool_count === 0) return "等待第一条路由"
  if (dashboard.value.healthy_pool_count === dashboard.value.pool_count) return "所有路由正常"
  if (dashboard.value.healthy_pool_count > 0) return "部分路由需要关注"
  return "当前没有可用路由"
})

const serviceDescription = computed(() => {
  if (!dashboard.value || dashboard.value.pool_count === 0) {
    return "创建账号池并添加 Tavily Key，运行状态会从这里开始汇聚。"
  }
  if (dashboard.value.healthy_pool_count === dashboard.value.pool_count) {
    return `${dashboard.value.pool_count} 个账号池正在稳定提供服务。`
  }
  return `${dashboard.value.healthy_pool_count} 个池可用，${dashboard.value.degraded_pool_count + dashboard.value.unavailable_pool_count} 个池需要处理。`
})

const serviceTone = computed(() => {
  if (!dashboard.value || dashboard.value.pool_count === 0) return "idle"
  if (dashboard.value.healthy_pool_count === dashboard.value.pool_count) return "normal"
  if (dashboard.value.healthy_pool_count > 0) return "warning"
  return "error"
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
  <div class="view-stack dashboard-view">
    <LoadingSkeleton v-if="loading" :rows="7" />
    <div v-else-if="error" class="inline-error" role="alert">
      <div>
        <strong>无法获取运行状态</strong>
        <p>{{ error }}</p>
      </div>
      <button class="button button--secondary" type="button" @click="load">重新加载</button>
    </div>

    <template v-else-if="dashboard">
      <div class="dashboard-frame">
        <div class="dashboard-primary">
          <section class="dashboard-health">
            <div
              class="service-emblem"
              :class="`service-emblem--${serviceTone}`"
              aria-hidden="true"
            >
              <span>{{ dashboard.healthy_pool_count }}/{{ dashboard.pool_count }}</span>
              <small>池在线</small>
            </div>
            <PageHeader :title="serviceState" :description="serviceDescription">
              <template #actions>
                <button
                  class="button button--quiet button--icon-mobile"
                  type="button"
                  :disabled="loading"
                  aria-label="刷新总览"
                  @click="load"
                >
                  <RefreshCw :size="16" :class="{ spin: loading }" />
                  <span>刷新</span>
                </button>
                <RouterLink class="button button--primary" to="/pools">
                  管理账号池 <ArrowUpRight :size="16" />
                </RouterLink>
              </template>
            </PageHeader>
          </section>

          <section class="metric-line" aria-label="核心运行指标">
            <div>
              <span>账号池健康</span>
              <strong
                >{{ dashboard.healthy_pool_count
                }}<small>/{{ dashboard.pool_count }}</small></strong
              >
              <p>
                {{
                  dashboard.degraded_pool_count
                    ? `${dashboard.degraded_pool_count} 个降级`
                    : "全部可用"
                }}
              </p>
            </div>
            <div>
              <span>可用 Tavily Key</span>
              <strong
                >{{ dashboard.available_key_count
                }}<small>/{{ dashboard.key_count }}</small></strong
              >
              <p>实时路由候选</p>
            </div>
            <div>
              <span>今日请求</span>
              <strong>{{ formatNumber(dashboard.requests_today) }}</strong>
              <p>{{ formatNumber(dashboard.successes_today) }} 次成功</p>
            </div>
            <div>
              <span>成功率</span>
              <strong>{{
                dashboard.requests_today ? `${dashboard.success_rate.toFixed(1)}%` : "—"
              }}</strong>
              <p>按外部请求统计</p>
            </div>
            <div>
              <span>平均耗时</span>
              <strong>{{ formatLatency(dashboard.average_latency_ms) }}</strong>
              <p>上游完整响应</p>
            </div>
          </section>

          <section class="routing-surface">
            <div class="section-heading">
              <div>
                <h2>实时路由</h2>
                <p>从账号池到 Tavily Search 的当前可用路径。</p>
              </div>
              <RouterLink to="/pools">查看所有池 <ArrowUpRight :size="14" /></RouterLink>
            </div>
            <RoutingMap v-if="pools.length" :pools="pools" />
            <EmptyState
              v-else
              title="还没有活动路由"
              description="创建账号池并添加 Tavily Key 后，路由会在这里点亮。"
            >
              <RouterLink class="button button--primary" to="/pools">创建账号池</RouterLink>
            </EmptyState>
          </section>

          <section class="data-surface pool-overview">
            <div class="section-heading">
              <div>
                <h2>账号池概览</h2>
                <p>池级健康、当前容量与今天的实际表现。</p>
              </div>
              <div class="capacity-note">
                <span>最高单 Key 可路由额度</span>
                <strong>{{ formatNumber(dashboard.estimated_remaining) }}</strong>
              </div>
            </div>

            <div v-if="pools.length" class="pool-table" role="table" aria-label="账号池概览">
              <div class="pool-table__head" role="row">
                <span>账号池</span><span>状态</span><span>Key</span><span>可路由额度</span
                ><span>今日表现</span><span></span>
              </div>
              <RouterLink
                v-for="pool in pools"
                :key="pool.id"
                :to="`/pools/${pool.id}`"
                class="pool-table__row"
                role="row"
              >
                <span class="pool-table__identity">
                  <span class="pool-dot" :class="`pool-dot--${pool.status}`"></span>
                  <span
                    ><strong>{{ pool.name }}</strong
                    ><small>{{
                      pool.description ||
                      (pool.strategy === "random" ? "随机可用 Key" : "剩余额度优先")
                    }}</small></span
                  >
                </span>
                <StatusBadge :status="pool.status" />
                <span class="table-metric"
                  ><strong>{{ pool.available_key_count }}/{{ pool.key_count }}</strong
                  ><small>可用</small></span
                >
                <span class="table-metric"
                  ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong
                  ><small>最高单 Key</small></span
                >
                <span class="table-metric"
                  ><strong>{{ formatNumber(pool.requests_today) }}</strong
                  ><small>{{ pool.success_rate_today.toFixed(1) }}% 成功</small></span
                >
                <ArrowUpRight :size="17" aria-hidden="true" />
              </RouterLink>
            </div>
            <EmptyState
              v-else
              title="还没有账号池"
              description="创建第一个池后，运行状态会在这里汇总。"
            />
          </section>
        </div>

        <aside class="activity-surface" aria-label="近期运行动态">
          <div class="section-heading">
            <div>
              <h2>运行动态</h2>
              <p>告警与最近请求按优先级汇总。</p>
            </div>
            <RouterLink to="/logs">全部</RouterLink>
          </div>

          <div v-if="dashboard.alerts.length" class="activity-group">
            <span class="activity-group__label">需要关注</span>
            <component
              :is="alert.pool_id ? RouterLink : 'div'"
              v-for="alert in dashboard.alerts.slice(0, 3)"
              :key="`${alert.code}-${alert.pool_id}-${alert.key_id}`"
              :to="alert.pool_id ? `/pools/${alert.pool_id}` : undefined"
              class="activity-record activity-record--alert"
            >
              <span class="activity-record__icon"><CircleAlert :size="16" /></span>
              <span
                ><strong>{{ alert.message }}</strong
                ><small>{{ alert.code }}</small></span
              >
              <ArrowUpRight v-if="alert.pool_id" :size="14" aria-hidden="true" />
            </component>
          </div>

          <div class="activity-group">
            <span class="activity-group__label">最近请求</span>
            <RouterLink
              v-for="log in logs?.items.slice(0, 5)"
              :key="log.id"
              to="/logs"
              class="activity-record"
            >
              <span
                class="activity-record__status"
                :class="{
                  'activity-record__status--error': !log.status_code || log.status_code >= 400,
                }"
              ></span>
              <span>
                <strong
                  ><code>{{ log.id.slice(0, 10) }}</code></strong
                >
                <small>{{ formatDate(log.created_at) }} · {{ log.attempt_count }} 次尝试</small>
              </span>
              <span class="activity-record__latency">{{ formatLatency(log.latency_ms) }}</span>
            </RouterLink>
            <p v-if="!logs?.items.length" class="activity-empty">还没有请求记录。</p>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>
