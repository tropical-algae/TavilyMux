<script setup lang="ts">
import { BookOpenText, Plus, RefreshCw, Trash2 } from "lucide-vue-next"
import { RouterLink } from "vue-router"

import type { TavilyKey } from "../types/api"
import { formatDate, formatNumber, successRate } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import QuotaMeter from "./QuotaMeter.vue"
import StatusBadge from "./StatusBadge.vue"
import UiButton from "./UiButton.vue"

defineProps<{
  poolId: string
  keys: TavilyKey[]
  busyKey: string
}>()

defineEmits<{
  add: []
  check: [key: TavilyKey]
  rename: [key: TavilyKey]
  toggle: [key: TavilyKey]
  delete: [key: TavilyKey]
}>()
</script>

<template>
  <div class="section-actions">
    <div>
      <h2>Tavily Keys</h2>
      <p>真实 Key 只加密保存，页面始终脱敏显示。</p>
    </div>
    <UiButton variant="primary" @click="$emit('add')"> <Plus :size="17" />添加 Key </UiButton>
  </div>
  <EmptyState
    v-if="keys.length === 0"
    title="池里还没有 Tavily Key"
    description="添加至少一个 Key 后，这个池才能接收搜索请求。"
  />
  <section v-else class="table-surface key-table-surface">
    <div class="table-wrap">
      <table class="key-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>API Key</th>
            <th>状态</th>
            <th>额度</th>
            <th>成功率</th>
            <th>最后检测</th>
            <th class="align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="key in keys" :key="key.id">
            <td>
              <strong class="key-name">{{ key.name }}</strong>
            </td>
            <td>
              <code class="key-token" :title="key.masked_key">{{ key.masked_key }}</code>
            </td>
            <td>
              <div class="cell-stack">
                <StatusBadge :status="key.status" />
                <small v-if="key.last_error">{{ key.last_error }}</small>
              </div>
            </td>
            <td>
              <div class="quota-cell">
                <strong class="quota-remaining">
                  剩余：{{ formatNumber(key.estimated_remaining) }}
                  <span>（{{ key.account_plan || "未知套餐" }}）</span>
                </strong>
                <QuotaMeter label="令牌额度" :usage="key.usage" :limit="key.usage_limit" />
                <QuotaMeter
                  label="账户额度"
                  :usage="key.account_plan_usage"
                  :limit="key.account_plan_limit"
                />
              </div>
            </td>
            <td>
              <div class="cell-stack">
                <strong>{{ successRate(key.success_count, key.request_count) }}</strong>
                <small>{{ key.request_count }} 次请求</small>
              </div>
            </td>
            <td>
              <div class="cell-stack">
                <strong>{{ formatDate(key.last_checked_at) }}</strong>
                <small>最后使用：{{ formatDate(key.last_used_at) }}</small>
              </div>
            </td>
            <td>
              <div class="row-actions key-table__actions">
                <button
                  class="icon-button"
                  type="button"
                  :disabled="busyKey === key.id"
                  :aria-label="`检测 ${key.name}`"
                  @click="$emit('check', key)"
                >
                  <RefreshCw :size="16" :class="{ spin: busyKey === key.id }" />
                </button>
                <RouterLink
                  class="icon-button"
                  :to="`/logs?pool_id=${poolId}&key_id=${key.id}`"
                  :aria-label="`查看 ${key.name} 的日志`"
                >
                  <BookOpenText :size="16" />
                </RouterLink>
                <UiButton size="small" @click="$emit('rename', key)">改名</UiButton>
                <UiButton size="small" @click="$emit('toggle', key)">
                  {{ key.enabled ? "停用" : "启用" }}
                </UiButton>
                <button
                  class="icon-button icon-button--danger"
                  type="button"
                  :aria-label="`删除 ${key.name}`"
                  @click="$emit('delete', key)"
                >
                  <Trash2 :size="16" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
