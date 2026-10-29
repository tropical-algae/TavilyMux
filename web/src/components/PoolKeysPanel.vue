<script setup lang="ts">
import { BookOpenText, Plus, RefreshCw, Trash2 } from "lucide-vue-next"
import { RouterLink } from "vue-router"

import { useI18n } from "../i18n"
import type { TavilyKey } from "../types/api"
import { formatDate, formatNumber, successRate } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import QuotaMeter from "./QuotaMeter.vue"
import StatusBadge from "./StatusBadge.vue"
import UiButton from "./UiButton.vue"

const { t } = useI18n()

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
      <h2>{{ t("pool.key.title") }}</h2>
      <p>{{ t("pool.key.maskedHint") }}</p>
    </div>
    <UiButton variant="primary" @click="$emit('add')">
      <Plus :size="17" />{{ t("pool.key.add") }}
    </UiButton>
  </div>
  <EmptyState
    v-if="keys.length === 0"
    :title="t('pool.key.empty')"
    :description="t('pool.key.emptyDescription')"
  />
  <section v-else class="table-surface key-table-surface">
    <div class="table-wrap key-table-scroll">
      <table class="key-table">
        <colgroup>
          <col class="key-table__col key-table__col--name" />
          <col class="key-table__col key-table__col--token" />
          <col class="key-table__col key-table__col--status" />
          <col class="key-table__col key-table__col--quota" />
          <col class="key-table__col key-table__col--success" />
          <col class="key-table__col key-table__col--checked" />
          <col class="key-table__col key-table__col--actions" />
        </colgroup>
        <thead>
          <tr>
            <th>{{ t("pool.key.name") }}</th>
            <th>API Key</th>
            <th>{{ t("pool.key.status") }}</th>
            <th>{{ t("pool.key.quota") }}</th>
            <th>{{ t("pool.key.successRate") }}</th>
            <th>{{ t("pool.key.lastCheck") }}</th>
            <th>{{ t("pool.key.operations") }}</th>
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
                  {{
                    t("pool.key.available", { value: formatNumber(key.estimated_remaining) })
                  }}
                  <span>（{{ key.account_plan || t("common.unknownPlan") }}）</span>
                </strong>
                <QuotaMeter
                  :label="t('pool.key.tokenQuota')"
                  :usage="key.usage"
                  :limit="key.usage_limit"
                />
                <QuotaMeter
                  :label="t('pool.key.accountQuota')"
                  :usage="key.account_plan_usage"
                  :limit="key.account_plan_limit"
                />
              </div>
            </td>
            <td>
              <div class="cell-stack">
                <strong>{{ successRate(key.success_count, key.request_count) }}</strong>
                <small>{{ t("pool.key.requestCount", { count: key.request_count }) }}</small>
              </div>
            </td>
            <td>
              <div class="cell-stack">
                <strong>{{ formatDate(key.last_checked_at) }}</strong>
                <small>{{
                  t("pool.key.lastUsed", { value: formatDate(key.last_used_at) })
                }}</small>
              </div>
            </td>
            <td>
              <div class="row-actions key-table__actions">
                <button
                  class="icon-button"
                  type="button"
                  :disabled="busyKey === key.id"
                  :aria-label="t('pool.key.checkLabel', { name: key.name })"
                  @click="$emit('check', key)"
                >
                  <RefreshCw :size="16" :class="{ spin: busyKey === key.id }" />
                </button>
                <RouterLink
                  class="icon-button"
                  :to="`/logs?pool_id=${poolId}&key_id=${key.id}`"
                  :aria-label="t('pool.key.logsLabel', { name: key.name })"
                >
                  <BookOpenText :size="16" />
                </RouterLink>
                <UiButton size="small" @click="$emit('rename', key)">{{
                  t("common.rename")
                }}</UiButton>
                <UiButton size="small" @click="$emit('toggle', key)">
                  {{ key.enabled ? t("pool.access.disable") : t("common.enable") }}
                </UiButton>
                <button
                  class="icon-button icon-button--danger"
                  type="button"
                  :aria-label="t('pool.key.deleteLabel', { name: key.name })"
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
