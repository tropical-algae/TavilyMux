<script setup lang="ts">
import { ArrowUpRight, Copy, Plus, RefreshCw } from "lucide-vue-next"
import { computed, onMounted, reactive, ref } from "vue"
import { RouterLink } from "vue-router"

import { api, errorMessage } from "../api/client"
import BaseModal from "../components/BaseModal.vue"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import SelectControl from "../components/SelectControl.vue"
import StatusBadge from "../components/StatusBadge.vue"
import UiButton from "../components/UiButton.vue"
import { useLoadingBoundary } from "../composables/useLoadingBoundary"
import { useI18n } from "../i18n"
import { useToastStore } from "../stores/toasts"
import type { CreatedPool, Dashboard, Pool, RoutingStrategy } from "../types/api"
import { formatDate, formatLatency, formatNumber } from "../utils/format"

const dashboard = ref<Dashboard | null>(null)
const { t } = useI18n()
const pools = ref<Pool[]>([])
const { loading, run: runLoad, showSkeleton } = useLoadingBoundary()
const saving = ref(false)
const createOpen = ref(false)
const loadError = ref("")
const formError = ref("")
const created = ref<CreatedPool | null>(null)
const toasts = useToastStore()
const routingOptions = computed(() => [
  { value: "max_remaining", label: t("form.routingMaxRemaining") },
  { value: "random", label: t("form.routingRandom") },
])
const form = reactive({
  name: "",
  description: "",
  strategy: "max_remaining" as RoutingStrategy,
  monitor_interval_seconds: 300,
  max_attempts: 3,
  concurrency_limit: null as number | null,
  rpm_limit: null as number | null,
  connection_override: false,
  upstream_base_url: "",
  http_proxy: "",
  https_proxy: "",
  allow_direct_fallback: false,
})

const searchExample = computed(() => {
  if (!created.value) return ""
  return [
    `curl ${window.location.origin}/search \\`,
    `  -H 'Authorization: Bearer ${created.value.relay_key}' \\`,
    "  -H 'Content-Type: application/json' \\",
    `  -d '{"query":"hello from TavilyMux"}'`,
  ].join("\n")
})

async function load(): Promise<void> {
  await runLoad(async () => {
    try {
      const [dashboardResponse, poolResponse] = await Promise.all([
        api.get<Dashboard>("/dashboard"),
        api.get<Pool[]>("/pools"),
      ])
      dashboard.value = dashboardResponse.data
      pools.value = poolResponse.data
      loadError.value = ""
    } catch (cause) {
      loadError.value = errorMessage(cause, t("dashboard.loadError"))
    }
  })
}

async function createPool(): Promise<void> {
  saving.value = true
  formError.value = ""
  try {
    const payload = {
      name: form.name,
      description: form.description || null,
      strategy: form.strategy,
      monitor_interval_seconds: form.monitor_interval_seconds,
      max_attempts: form.max_attempts,
      concurrency_limit: form.concurrency_limit,
      rpm_limit: form.rpm_limit,
      ...(form.connection_override
        ? {
            upstream_base_url: form.upstream_base_url || null,
            http_proxy: form.http_proxy || null,
            https_proxy: form.https_proxy || null,
            allow_direct_fallback: form.allow_direct_fallback,
          }
        : {}),
    }
    const response = await api.post<CreatedPool>("/pools", payload)
    created.value = response.data
    createOpen.value = false
    form.name = ""
    form.description = ""
    form.connection_override = false
    form.upstream_base_url = ""
    form.http_proxy = ""
    form.https_proxy = ""
    form.allow_direct_fallback = false
    toasts.show(t("dashboard.created"), "success")
    await load()
  } catch (cause) {
    formError.value = errorMessage(cause, t("dashboard.createError"))
  } finally {
    saving.value = false
  }
}

async function copyKey(): Promise<void> {
  if (!created.value) return
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable")
    await navigator.clipboard.writeText(created.value.relay_key)
    toasts.show(t("dashboard.copied"), "success")
  } catch {
    toasts.show(t("common.copyFailed"), "error")
  }
}

onMounted(load)
</script>

<template>
  <div class="view-stack pools-workspace">
    <PageHeader :title="t('dashboard.title')" :description="t('dashboard.description')">
      <template #actions>
        <UiButton
          class="button--icon-mobile"
          :disabled="loading"
          :aria-label="t('common.refresh')"
          @click="load"
        >
          <RefreshCw :size="16" :class="{ spin: loading }" />
          <span>{{ t("common.refresh") }}</span>
        </UiButton>
        <UiButton variant="primary" @click="createOpen = true">
          <Plus :size="17" />{{ t("dashboard.create") }}
        </UiButton>
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="loadError" class="inline-error" role="alert">
      <div>
        <strong>{{ t("dashboard.loadErrorTitle") }}</strong>
        <p>{{ loadError }}</p>
      </div>
      <UiButton @click="load">{{ t("common.retry") }}</UiButton>
    </div>

    <template v-else-if="dashboard">
      <section class="metric-line" :aria-label="t('dashboard.metricLabel')">
        <div>
          <span>{{ t("dashboard.healthyPools") }}</span>
          <strong
            >{{ dashboard.healthy_pool_count
            }}<small> / {{ dashboard.pool_count }}</small></strong
          >
          <p>
            {{
              dashboard.degraded_pool_count
                ? t("dashboard.degradedCount", { count: dashboard.degraded_pool_count })
                : t("dashboard.allAvailable")
            }}
          </p>
        </div>
        <div>
          <span>{{ t("dashboard.availableKeys") }}</span>
          <strong
            >{{ dashboard.available_key_count
            }}<small> / {{ dashboard.key_count }}</small></strong
          >
          <p>{{ t("dashboard.currentCandidates") }}</p>
        </div>
        <div>
          <span>{{ t("dashboard.requestsToday") }}</span>
          <strong>{{ formatNumber(dashboard.requests_today) }}</strong>
          <p>
            {{
              t("dashboard.successCount", { count: formatNumber(dashboard.successes_today) })
            }}
          </p>
        </div>
        <div>
          <span>{{ t("dashboard.successRate") }}</span>
          <strong>{{
            dashboard.requests_today ? `${dashboard.success_rate.toFixed(1)}%` : "—"
          }}</strong>
          <p>{{ t("dashboard.successRateHint") }}</p>
        </div>
        <div>
          <span>{{ t("dashboard.averageLatency") }}</span>
          <strong>{{ formatLatency(dashboard.average_latency_ms) }}</strong>
          <p>{{ t("dashboard.upstreamResponse") }}</p>
        </div>
      </section>

      <section v-if="created" class="one-time-secret" aria-labelledby="secret-title">
        <div>
          <h2 id="secret-title">{{ t("dashboard.secretOnce") }}</h2>
          <p>{{ t("dashboard.secretHint") }}</p>
        </div>
        <code>{{ created.relay_key }}</code>
        <div class="one-time-secret__actions">
          <UiButton variant="primary" @click="copyKey">
            <Copy :size="16" />{{ t("dashboard.copyKey") }}
          </UiButton>
          <UiButton variant="ghost" @click="created = null">
            {{ t("dashboard.saved") }}
          </UiButton>
        </div>
      </section>
      <section v-if="created" class="relay-example" :aria-label="t('dashboard.searchExample')">
        <div>
          <strong>{{ t("dashboard.testNow") }}</strong>
          <span>{{ t("dashboard.testNowHint") }}</span>
        </div>
        <pre><code>{{ searchExample }}</code></pre>
      </section>

      <div class="database-toolbar">
        <strong>{{ t("dashboard.allPools") }}</strong>
        <span>{{ t("dashboard.poolCount", { count: pools.length }) }}</span>
      </div>

      <EmptyState
        v-if="pools.length === 0"
        :title="t('dashboard.empty')"
        :description="t('dashboard.emptyDescription')"
      >
        <UiButton variant="primary" @click="createOpen = true">
          {{ t("dashboard.create") }}
        </UiButton>
      </EmptyState>
      <section v-else class="pool-directory">
        <RouterLink
          v-for="pool in pools"
          :key="pool.id"
          :to="`/pools/${pool.id}`"
          class="pool-record"
        >
          <div class="pool-record__identity">
            <span
              class="pool-record__signal"
              :class="`pool-record__signal--${pool.status}`"
            ></span>
            <div>
              <strong>{{ pool.name }}</strong>
              <p>{{ pool.description || t("dashboard.noDescription") }}</p>
              <small>{{
                t("dashboard.lastUsed", { value: formatDate(pool.last_used_at) })
              }}</small>
            </div>
          </div>
          <StatusBadge :status="pool.status" />
          <div class="pool-record__metric">
            <span>{{ t("pool.overview.availableKeys") }}</span
            ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
          </div>
          <div class="pool-record__metric">
            <span>{{ t("dashboard.highestQuota") }}</span
            ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
          </div>
          <div class="pool-record__metric">
            <span>{{ t("dashboard.requestsAndRate") }}</span>
            <strong
              >{{ formatNumber(pool.requests_today) }} /
              {{ pool.success_rate_today.toFixed(1) }}%</strong
            >
          </div>
          <ArrowUpRight :size="18" aria-hidden="true" />
        </RouterLink>
      </section>
    </template>

    <BaseModal
      :open="createOpen"
      :title="t('dashboard.create')"
      :description="t('dashboard.createDescription')"
      size="large"
      :dismissible="!saving"
      @close="createOpen = false"
    >
      <form id="create-pool-form" class="form-panel" @submit.prevent="createPool">
        <div class="form-grid">
          <label class="field">
            <span>{{ t("dashboard.poolName") }}</span>
            <input
              v-model.trim="form.name"
              required
              maxlength="100"
              :placeholder="t('dashboard.poolNamePlaceholder')"
            />
          </label>
          <div class="field">
            <span>{{ t("dashboard.routingStrategy") }}</span>
            <SelectControl v-model="form.strategy" :options="routingOptions" />
          </div>
          <label class="field field--span">
            <span>{{ t("dashboard.poolDescription") }}</span>
            <textarea
              v-model.trim="form.description"
              rows="2"
              :placeholder="t('dashboard.poolDescriptionPlaceholder')"
            />
          </label>
          <label class="field">
            <span>{{ t("form.monitorInterval") }}</span>
            <input
              v-model.number="form.monitor_interval_seconds"
              type="number"
              min="60"
              max="86400"
            />
          </label>
          <label class="field">
            <span>{{ t("form.maxAttempts") }}</span>
            <input v-model.number="form.max_attempts" type="number" min="1" max="10" />
          </label>
          <label class="field">
            <span>{{ t("form.concurrencyLimit") }}</span>
            <input
              v-model.number="form.concurrency_limit"
              type="number"
              min="1"
              :placeholder="t('common.noLimit')"
            />
          </label>
          <label class="field">
            <span>{{ t("form.rpmLimit") }}</span>
            <input
              v-model.number="form.rpm_limit"
              type="number"
              min="1"
              :placeholder="t('common.noLimit')"
            />
          </label>
        </div>
        <label class="switch-field">
          <input v-model="form.connection_override" type="checkbox" />
          <span
            ><strong>{{ t("dashboard.connectionOverride") }}</strong
            ><small>{{ t("dashboard.connectionOverrideHint") }}</small></span
          >
        </label>
        <div v-if="form.connection_override" class="form-grid">
          <label class="field field--span">
            <span>{{ t("form.tavilyBaseUrl") }}</span>
            <input
              v-model.trim="form.upstream_base_url"
              type="url"
              placeholder="https://api.tavily.com"
            />
          </label>
          <label class="field">
            <span>{{ t("form.httpProxy") }}</span>
            <input
              v-model.trim="form.http_proxy"
              type="url"
              placeholder="http://127.0.0.1:7890"
            />
          </label>
          <label class="field">
            <span>{{ t("form.httpsProxy") }}</span>
            <input
              v-model.trim="form.https_proxy"
              type="url"
              placeholder="http://127.0.0.1:7890"
            />
          </label>
          <label class="switch-field field--span">
            <input v-model="form.allow_direct_fallback" type="checkbox" />
            <span
              ><strong>{{ t("dashboard.directFallback") }}</strong
              ><small>{{ t("dashboard.directFallbackHint") }}</small></span
            >
          </label>
        </div>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="saving" @click="createOpen = false">
          {{ t("common.cancel") }}
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="create-pool-form"
          :disabled="saving || !form.name"
        >
          {{ saving ? t("dashboard.creating") : t("dashboard.createAndGenerate") }}
        </UiButton>
      </template>
    </BaseModal>
  </div>
</template>
