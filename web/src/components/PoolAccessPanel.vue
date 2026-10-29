<script setup lang="ts">
import { CheckCircle2, Copy, KeyRound, Plus, Trash2 } from "lucide-vue-next"

import type { CreatedRelayKey, RelayKey } from "../types/api"
import { useI18n } from "../i18n"
import { formatDate } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import StatusBadge from "./StatusBadge.vue"
import UiButton from "./UiButton.vue"

const { t } = useI18n()

defineProps<{
  relayKeys: RelayKey[]
  oneTimeRelay: CreatedRelayKey | null
}>()

defineEmits<{
  create: []
  copy: []
  dismissSecret: []
  toggle: [relay: RelayKey]
  delete: [relay: RelayKey]
}>()
</script>

<template>
  <div class="section-actions">
    <div>
      <h2>{{ t("pool.access.title") }}</h2>
      <p>{{ t("pool.access.description") }}</p>
    </div>
    <UiButton variant="primary" @click="$emit('create')">
      <Plus :size="17" />{{ t("pool.access.generate") }}
    </UiButton>
  </div>
  <section v-if="oneTimeRelay" class="one-time-secret">
    <div>
      <h2>{{ t("pool.access.secretOnce") }}</h2>
      <p>{{ t("pool.access.secretHint") }}</p>
    </div>
    <code>{{ oneTimeRelay.relay_key }}</code>
    <div class="one-time-secret__actions">
      <UiButton variant="primary" @click="$emit('copy')">
        <Copy :size="16" />{{ t("common.copy") }}
      </UiButton>
      <UiButton variant="ghost" @click="$emit('dismissSecret')">
        <CheckCircle2 :size="16" />{{ t("pool.access.saved") }}
      </UiButton>
    </div>
  </section>
  <EmptyState
    v-if="relayKeys.length === 0"
    :title="t('pool.access.empty')"
    :description="t('pool.access.emptyDescription')"
  />
  <div v-else class="credential-list">
    <article v-for="relay in relayKeys" :key="relay.id" class="credential-record">
      <div class="credential-record__identity">
        <span class="credential-record__icon"><KeyRound :size="18" /></span>
        <div>
          <strong>{{ relay.name }}</strong>
          <code>{{ relay.prefix }}_••••••••</code>
        </div>
      </div>
      <div class="credential-record__last-used">
        <span>{{ t("pool.access.lastUsed") }}</span>
        <strong>{{ formatDate(relay.last_used_at) }}</strong>
      </div>
      <StatusBadge :status="relay.enabled ? 'available' : 'disabled'" />
      <div class="row-actions">
        <UiButton size="small" @click="$emit('toggle', relay)">
          {{ relay.enabled ? t("pool.access.disable") : t("common.enable") }}
        </UiButton>
        <button
          class="icon-button icon-button--danger"
          type="button"
          :aria-label="t('pool.access.revokeLabel', { name: relay.name })"
          @click="$emit('delete', relay)"
        >
          <Trash2 :size="16" />
        </button>
      </div>
    </article>
  </div>
</template>
