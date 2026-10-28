<script setup lang="ts">
import { CheckCircle2, Copy, KeyRound, Plus, Trash2 } from "lucide-vue-next"

import type { CreatedRelayKey, RelayKey } from "../types/api"
import { formatDate } from "../utils/format"
import EmptyState from "./EmptyState.vue"
import StatusBadge from "./StatusBadge.vue"
import UiButton from "./UiButton.vue"

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
      <h2>中转凭证</h2>
      <p>调用方通过 Bearer 中转 Key 访问本服务的 /search。</p>
    </div>
    <UiButton variant="primary" @click="$emit('create')">
      <Plus :size="17" />生成凭证
    </UiButton>
  </div>
  <section v-if="oneTimeRelay" class="one-time-secret">
    <div>
      <h2>新 Key 只显示这一次</h2>
      <p>复制后安全地交给调用方。</p>
    </div>
    <code>{{ oneTimeRelay.relay_key }}</code>
    <div class="one-time-secret__actions">
      <UiButton variant="primary" @click="$emit('copy')"> <Copy :size="16" />复制 </UiButton>
      <UiButton variant="ghost" @click="$emit('dismissSecret')">
        <CheckCircle2 :size="16" />我已保存
      </UiButton>
    </div>
  </section>
  <EmptyState
    v-if="relayKeys.length === 0"
    title="还没有中转凭证"
    description="生成凭证后，调用方才能通过这个账号池访问 /search。"
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
        <span>最近使用</span>
        <strong>{{ formatDate(relay.last_used_at) }}</strong>
      </div>
      <StatusBadge :status="relay.enabled ? 'available' : 'disabled'" />
      <div class="row-actions">
        <UiButton size="small" @click="$emit('toggle', relay)">
          {{ relay.enabled ? "停用" : "启用" }}
        </UiButton>
        <button
          class="icon-button icon-button--danger"
          type="button"
          :aria-label="`吊销 ${relay.name}`"
          @click="$emit('delete', relay)"
        >
          <Trash2 :size="16" />
        </button>
      </div>
    </article>
  </div>
</template>
