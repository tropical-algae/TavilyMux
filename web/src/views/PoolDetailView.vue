<script setup lang="ts">
import {
  Activity,
  ArrowLeft,
  BookOpenText,
  KeyRound,
  Settings,
  ShieldCheck,
} from "lucide-vue-next"
import { computed, onMounted, reactive, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { api, errorMessage } from "../api/client"
import BaseModal from "../components/BaseModal.vue"
import ConfirmModal from "../components/ConfirmModal.vue"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import PoolAccessPanel from "../components/PoolAccessPanel.vue"
import PoolKeysPanel from "../components/PoolKeysPanel.vue"
import PoolOverviewPanel from "../components/PoolOverviewPanel.vue"
import PoolSettingsPanel from "../components/PoolSettingsPanel.vue"
import RequestLogList from "../components/RequestLogList.vue"
import StatusBadge from "../components/StatusBadge.vue"
import UiButton from "../components/UiButton.vue"
import { useLoadingBoundary } from "../composables/useLoadingBoundary"
import { useI18n } from "../i18n"
import { useToastStore } from "../stores/toasts"
import type {
  CreatedRelayKey,
  PaginatedLogs,
  Pool,
  RelayKey,
  TavilyKey,
  UsageSnapshot,
} from "../types/api"

type Tab = "overview" | "keys" | "logs" | "access" | "settings"

const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const poolId = computed(() => String(route.params.id))
const pool = ref<Pool | null>(null)
const keys = ref<TavilyKey[]>([])
const relayKeys = ref<RelayKey[]>([])
const logs = ref<PaginatedLogs | null>(null)
const snapshots = ref<UsageSnapshot[]>([])
const selectedKeyId = ref("")
const activeTab = ref<Tab>("overview")
const expandedLogs = ref(new Set<string>())
const { run: runLoad, showSkeleton } = useLoadingBoundary()
const { run: runUsageLoad, showSkeleton: showUsageSkeleton } = useLoadingBoundary({
  skeletonOnRefresh: true,
})
const busyKey = ref("")
const error = ref("")
const keyFormOpen = ref(false)
const relayFormOpen = ref(false)
const deletePoolOpen = ref(false)
const addingKeys = ref(false)
const creatingRelay = ref(false)
const deletingPool = ref(false)
const renamingKey = ref<TavilyKey | null>(null)
const renameKeyName = ref("")
const savingKeyName = ref(false)
const destructiveTarget = ref<
  { kind: "key"; item: TavilyKey } | { kind: "relay"; item: RelayKey } | null
>(null)
const deletingTarget = ref(false)
const keyMode = ref<"single" | "bulk">("single")
const keyForm = reactive({ name: "", api_key: "", bulk: "" })
const relayName = ref("")
const oneTimeRelay = ref<CreatedRelayKey | null>(null)
const toasts = useToastStore()
const hydratingUsage = ref(false)

const canAddKeys = computed(() =>
  keyMode.value === "single"
    ? Boolean(keyForm.name && keyForm.api_key)
    : Boolean(keyForm.bulk.trim()),
)
const destructiveCopy = computed(() => {
  const target = destructiveTarget.value
  if (!target) return null
  if (target.kind === "key") {
    return {
      title: t("pool.detail.deleteKey"),
      description: t("pool.detail.confirmDeleteKey", { name: target.item.name }),
      warningTitle: t("pool.detail.deleteWarningTitle"),
      warningDescription: t("pool.detail.deleteKeyWarning"),
      confirmLabel: t("pool.detail.deleteKeyConfirm"),
    }
  }
  return {
    title: t("pool.detail.revoke"),
    description: t("pool.detail.confirmRevoke", { name: target.item.name }),
    warningTitle: t("pool.detail.revokeWarningTitle"),
    warningDescription: t("pool.detail.revokeWarning"),
    confirmLabel: t("pool.detail.revokeConfirm"),
  }
})

const tabs = computed<{ id: Tab; label: string; icon: typeof Activity }[]>(() => [
  { id: "overview", label: t("pool.detail.tabOverview"), icon: Activity },
  { id: "keys", label: t("pool.detail.tabKeys"), icon: KeyRound },
  { id: "logs", label: t("pool.detail.tabLogs"), icon: BookOpenText },
  { id: "access", label: t("pool.detail.tabAccess"), icon: ShieldCheck },
  { id: "settings", label: t("pool.detail.tabSettings"), icon: Settings },
])

async function load(): Promise<void> {
  await runLoad(async () => {
    try {
      const [poolResponse, keyResponse, relayResponse, logResponse] = await Promise.all([
        api.get<Pool>(`/pools/${poolId.value}`),
        api.get<TavilyKey[]>(`/pools/${poolId.value}/keys`),
        api.get<RelayKey[]>(`/pools/${poolId.value}/relay-keys`),
        api.get<PaginatedLogs>("/logs", {
          params: { pool_id: poolId.value, page_size: 8 },
        }),
      ])
      const selectedKey =
        keyResponse.data.find((key) => key.id === selectedKeyId.value) ?? keyResponse.data[0]
      const usage = selectedKey
        ? await api
            .get<UsageSnapshot[]>(`/pools/${poolId.value}/keys/${selectedKey.id}/usage`)
            .then((response) => response.data)
            .catch(() => [])
        : []

      pool.value = poolResponse.data
      keys.value = keyResponse.data
      relayKeys.value = relayResponse.data
      logs.value = logResponse.data
      hydratingUsage.value = true
      selectedKeyId.value = selectedKey?.id ?? ""
      snapshots.value = usage
      hydratingUsage.value = false
      error.value = ""
    } catch (cause) {
      error.value = errorMessage(cause, t("pool.detail.loadError"))
    }
  })
}

async function loadUsage(keyId: string): Promise<void> {
  await runUsageLoad(async () => {
    if (!keyId) {
      snapshots.value = []
      return
    }
    try {
      snapshots.value = (
        await api.get<UsageSnapshot[]>(`/pools/${poolId.value}/keys/${keyId}/usage`)
      ).data
    } catch {
      snapshots.value = []
    }
  })
}

async function addKeys(): Promise<void> {
  addingKeys.value = true
  try {
    if (keyMode.value === "single") {
      const response = await api.post<TavilyKey>(`/pools/${poolId.value}/keys`, {
        name: keyForm.name,
        api_key: keyForm.api_key,
      })
      keys.value.push(response.data)
    } else {
      const parsed = keyForm.bulk
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line, index) => {
          const separator = line.indexOf(",")
          return separator > 0
            ? {
                name: line.slice(0, separator).trim(),
                api_key: line.slice(separator + 1).trim(),
              }
            : { name: `Key ${keys.value.length + index + 1}`, api_key: line }
        })
      const response = await api.post<TavilyKey[]>(`/pools/${poolId.value}/keys/bulk`, {
        keys: parsed,
      })
      keys.value.push(...response.data)
    }
    keyForm.name = ""
    keyForm.api_key = ""
    keyForm.bulk = ""
    keyFormOpen.value = false
    toasts.show(t("pool.detail.addSuccess"), "success")
    await load()
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.addError")), "error")
  } finally {
    addingKeys.value = false
  }
}

async function checkKey(key: TavilyKey): Promise<void> {
  busyKey.value = key.id
  try {
    const checked = await api.post<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}/check`)
    const index = keys.value.findIndex((item) => item.id === key.id)
    if (index >= 0) keys.value[index] = checked.data
    if (selectedKeyId.value === key.id) await loadUsage(key.id)
    if (checked.data.status === "check_failed") {
      toasts.show(
        t("pool.detail.checkFailed", {
          error: checked.data.last_error ?? t("pool.detail.checkFailedFallback"),
        }),
        "error",
      )
    } else if (checked.data.status === "invalid") {
      toasts.show(t("pool.detail.checkInvalid"), "error")
    } else if (checked.data.status === "exhausted") {
      toasts.show(t("pool.detail.checkExhausted"), "info")
    } else if (checked.data.status === "rate_limited") {
      toasts.show(t("pool.detail.checkRateLimited"), "info")
    } else {
      toasts.show(t("pool.detail.checkSuccess"), "success")
    }
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.checkConnectionError")), "error")
  } finally {
    busyKey.value = ""
  }
}

function openRenameKey(key: TavilyKey): void {
  renamingKey.value = key
  renameKeyName.value = key.name
}

async function saveKeyName(): Promise<void> {
  const key = renamingKey.value
  const name = renameKeyName.value.trim()
  if (!key || !name || name === key.name) {
    renamingKey.value = null
    return
  }
  savingKeyName.value = true
  try {
    const updated = await api.patch<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}`, {
      name,
    })
    Object.assign(key, updated.data)
    renamingKey.value = null
    toasts.show(t("pool.detail.keyNameUpdated"), "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.keyNameError")), "error")
  } finally {
    savingKeyName.value = false
  }
}

async function toggleKey(key: TavilyKey): Promise<void> {
  try {
    const updated = await api.patch<TavilyKey>(`/pools/${poolId.value}/keys/${key.id}`, {
      enabled: !key.enabled,
    })
    Object.assign(key, updated.data)
    toasts.show(
      key.enabled ? t("pool.detail.keyEnabled") : t("pool.detail.keyDisabled"),
      "success",
    )
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.keyStatusError")), "error")
  }
}

function requestDeleteKey(key: TavilyKey): void {
  destructiveTarget.value = { kind: "key", item: key }
}

async function createRelay(): Promise<void> {
  creatingRelay.value = true
  try {
    const response = await api.post<CreatedRelayKey>(`/pools/${poolId.value}/relay-keys`, {
      name: relayName.value,
    })
    oneTimeRelay.value = response.data
    relayKeys.value.unshift(response.data)
    relayName.value = ""
    relayFormOpen.value = false
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.relayGenerateError")), "error")
  } finally {
    creatingRelay.value = false
  }
}

async function toggleRelay(relay: RelayKey): Promise<void> {
  try {
    const response = await api.patch<RelayKey>(
      `/pools/${poolId.value}/relay-keys/${relay.id}`,
      { enabled: !relay.enabled },
    )
    Object.assign(relay, response.data)
    toasts.show(
      relay.enabled ? t("pool.detail.relayEnabled") : t("pool.detail.relayDisabled"),
      "success",
    )
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.relayStatusError")), "error")
  }
}

function requestDeleteRelay(relay: RelayKey): void {
  destructiveTarget.value = { kind: "relay", item: relay }
}

async function confirmTargetDeletion(): Promise<void> {
  const target = destructiveTarget.value
  if (!target) return
  deletingTarget.value = true
  try {
    if (target.kind === "key") {
      await api.delete(`/pools/${poolId.value}/keys/${target.item.id}`)
      keys.value = keys.value.filter((item) => item.id !== target.item.id)
      toasts.show(t("pool.detail.keyDeleted"), "success")
    } else {
      await api.delete(`/pools/${poolId.value}/relay-keys/${target.item.id}`)
      relayKeys.value = relayKeys.value.filter((item) => item.id !== target.item.id)
      toasts.show(t("pool.detail.relayRevoked"), "success")
    }
    destructiveTarget.value = null
  } catch (cause) {
    toasts.show(
      errorMessage(
        cause,
        target.kind === "key"
          ? t("pool.detail.keyDeleteError")
          : t("pool.detail.relayRevokeError"),
      ),
      "error",
    )
  } finally {
    deletingTarget.value = false
  }
}

async function copyRelay(): Promise<void> {
  if (!oneTimeRelay.value) return
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable")
    await navigator.clipboard.writeText(oneTimeRelay.value.relay_key)
    toasts.show(t("pool.detail.relayCopied"), "success")
  } catch {
    toasts.show(t("common.copyFailed"), "error")
  }
}

async function saveSettings(
  payload: Record<string, string | number | boolean | null>,
): Promise<void> {
  try {
    pool.value = (await api.patch<Pool>(`/pools/${poolId.value}`, payload)).data
    toasts.show(t("pool.detail.settingsSaved"), "success")
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.settingsSaveError")), "error")
  }
}

async function deletePool(): Promise<void> {
  if (!pool.value) return
  deletingPool.value = true
  try {
    await api.delete(`/pools/${poolId.value}`)
    deletePoolOpen.value = false
    toasts.show(t("pool.detail.poolDeleted"), "success")
    await router.push("/")
  } catch (cause) {
    toasts.show(errorMessage(cause, t("pool.detail.poolDeleteError")), "error")
  } finally {
    deletingPool.value = false
  }
}

function toggleLog(logId: string): void {
  const next = new Set(expandedLogs.value)
  if (next.has(logId)) next.delete(logId)
  else next.add(logId)
  expandedLogs.value = next
}

watch(
  selectedKeyId,
  (value) => {
    if (!hydratingUsage.value) void loadUsage(value)
  },
  { flush: "sync" },
)
onMounted(load)
</script>

<template>
  <div class="view-stack pool-detail-view">
    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error" class="inline-error">
      <p>{{ error }}</p>
      <UiButton @click="load">{{ t("common.retry") }}</UiButton>
    </div>
    <template v-else-if="pool">
      <RouterLink class="back-link" to="/"
        ><ArrowLeft :size="16" />{{ t("common.back") }}</RouterLink
      >
      <PageHeader
        :title="pool.name"
        :description="pool.description || t('pool.detail.emptyDescription')"
      >
        <template #actions><StatusBadge :status="pool.status" /></template>
      </PageHeader>

      <nav class="tabs" role="tablist" :aria-label="t('layout.page.poolDetail')">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" :size="17" />{{ tab.label }}
        </button>
      </nav>

      <PoolOverviewPanel
        v-if="activeTab === 'overview'"
        v-model:selected-key-id="selectedKeyId"
        :pool="pool"
        :keys="keys"
        :logs="logs"
        :snapshots="snapshots"
        :show-usage-skeleton="showUsageSkeleton"
      />

      <PoolKeysPanel
        v-else-if="activeTab === 'keys'"
        :pool-id="poolId"
        :keys="keys"
        :busy-key="busyKey"
        @add="keyFormOpen = true"
        @check="checkKey"
        @rename="openRenameKey"
        @toggle="toggleKey"
        @delete="requestDeleteKey"
      />

      <template v-else-if="activeTab === 'logs'">
        <div class="section-actions">
          <div>
            <h2>{{ t("pool.detail.logsTitle") }}</h2>
            <p>{{ t("pool.detail.logsDescription") }}</p>
          </div>
          <RouterLink class="button button--secondary" :to="`/logs?pool_id=${poolId}`">
            {{ t("pool.detail.viewAllLogs") }}
          </RouterLink>
        </div>
        <EmptyState
          v-if="!logs?.items.length"
          :title="t('pool.detail.logsEmpty')"
          :description="t('pool.detail.logsEmptyDescription')"
        />
        <RequestLogList
          v-else
          :logs="logs.items"
          :expanded="expandedLogs"
          @toggle="toggleLog"
        />
      </template>

      <PoolAccessPanel
        v-else-if="activeTab === 'access'"
        :relay-keys="relayKeys"
        :one-time-relay="oneTimeRelay"
        @create="relayFormOpen = true"
        @copy="copyRelay"
        @dismiss-secret="oneTimeRelay = null"
        @toggle="toggleRelay"
        @delete="requestDeleteRelay"
      />

      <PoolSettingsPanel
        v-else
        :pool="pool"
        @save="saveSettings"
        @delete="deletePoolOpen = true"
      />
    </template>

    <BaseModal
      :open="keyFormOpen"
      :title="t('pool.detail.addKey')"
      :description="t('pool.detail.addDescription')"
      size="large"
      :dismissible="!addingKeys"
      @close="keyFormOpen = false"
    >
      <form id="add-key-form" class="form-panel" @submit.prevent="addKeys">
        <div class="segmented">
          <button
            type="button"
            :class="{ active: keyMode === 'single' }"
            @click="keyMode = 'single'"
          >
            {{ t("pool.detail.addSingle") }}
          </button>
          <button
            type="button"
            :class="{ active: keyMode === 'bulk' }"
            @click="keyMode = 'bulk'"
          >
            {{ t("pool.detail.addBulk") }}
          </button>
        </div>
        <div v-if="keyMode === 'single'" class="form-grid">
          <label class="field">
            <span>{{ t("pool.detail.name") }}</span>
            <input
              v-model.trim="keyForm.name"
              required
              :placeholder="t('pool.detail.namePlaceholder')"
            />
          </label>
          <label class="field">
            <span>Tavily API Key</span>
            <input
              v-model.trim="keyForm.api_key"
              type="password"
              required
              autocomplete="off"
              placeholder="tvly-…"
            />
          </label>
        </div>
        <label v-else class="field">
          <span>{{ t("pool.detail.bulkHint") }}</span>
          <textarea
            v-model="keyForm.bulk"
            rows="7"
            required
            :placeholder="t('pool.detail.bulkPlaceholder')"
          />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="addingKeys" @click="keyFormOpen = false">
          {{ t("common.cancel") }}
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="add-key-form"
          :disabled="addingKeys || !canAddKeys"
        >
          {{ addingKeys ? t("pool.detail.adding") : t("pool.detail.addSubmit") }}
        </UiButton>
      </template>
    </BaseModal>

    <BaseModal
      :open="relayFormOpen"
      :title="t('pool.detail.generateCredential')"
      :description="t('pool.detail.relayOnce')"
      size="small"
      :dismissible="!creatingRelay"
      @close="relayFormOpen = false"
    >
      <form id="create-relay-form" class="form-panel" @submit.prevent="createRelay">
        <label class="field">
          <span>{{ t("pool.detail.credentialName") }}</span>
          <input
            v-model.trim="relayName"
            required
            autofocus
            :placeholder="t('pool.detail.credentialPlaceholder')"
          />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="creatingRelay" @click="relayFormOpen = false">
          {{ t("common.cancel") }}
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="create-relay-form"
          :disabled="creatingRelay || !relayName"
        >
          {{ creatingRelay ? t("pool.detail.generating") : t("pool.access.generate") }}
        </UiButton>
      </template>
    </BaseModal>

    <BaseModal
      :open="Boolean(renamingKey)"
      :title="t('pool.detail.renameKey')"
      :description="t('pool.detail.renameDescription')"
      size="small"
      :dismissible="!savingKeyName"
      @close="renamingKey = null"
    >
      <form id="rename-key-form" class="form-panel" @submit.prevent="saveKeyName">
        <label class="field">
          <span>{{ t("pool.detail.keyName") }}</span>
          <input v-model.trim="renameKeyName" required autofocus maxlength="100" />
        </label>
      </form>
      <template #footer>
        <UiButton variant="ghost" :disabled="savingKeyName" @click="renamingKey = null">
          {{ t("common.cancel") }}
        </UiButton>
        <UiButton
          variant="primary"
          type="submit"
          form="rename-key-form"
          :disabled="savingKeyName || !renameKeyName.trim()"
        >
          {{ savingKeyName ? t("pool.detail.savingName") : t("pool.detail.saveName") }}
        </UiButton>
      </template>
    </BaseModal>

    <ConfirmModal
      :open="deletePoolOpen"
      :title="t('pool.detail.deletePool')"
      :description="pool ? t('pool.detail.confirmDeletePool', { name: pool.name }) : undefined"
      :warning-title="t('pool.detail.deleteWarningTitle')"
      :warning-description="t('pool.detail.deletePoolWarning')"
      :confirm-label="t('pool.detail.deletePoolConfirm')"
      :busy="deletingPool"
      @close="deletePoolOpen = false"
      @confirm="deletePool"
    />

    <ConfirmModal
      v-if="destructiveCopy"
      :open="Boolean(destructiveTarget)"
      :title="destructiveCopy.title"
      :description="destructiveCopy.description"
      :warning-title="destructiveCopy.warningTitle"
      :warning-description="destructiveCopy.warningDescription"
      :confirm-label="destructiveCopy.confirmLabel"
      :busy="deletingTarget"
      @close="destructiveTarget = null"
      @confirm="confirmTargetDeletion"
    />
  </div>
</template>
