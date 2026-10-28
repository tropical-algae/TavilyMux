<script setup lang="ts">
import { TriangleAlert } from "lucide-vue-next"

import BaseModal from "./BaseModal.vue"
import UiButton from "./UiButton.vue"

withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    warningTitle: string
    warningDescription: string
    confirmLabel: string
    busy?: boolean
  }>(),
  {
    description: undefined,
    busy: false,
  },
)

defineEmits<{
  close: []
  confirm: []
}>()
</script>

<template>
  <BaseModal
    :open="open"
    :title="title"
    :description="description"
    size="small"
    :dismissible="!busy"
    @close="$emit('close')"
  >
    <div class="destructive-confirmation">
      <span><TriangleAlert :size="19" /></span>
      <div>
        <strong>{{ warningTitle }}</strong>
        <p>{{ warningDescription }}</p>
      </div>
    </div>
    <template #footer>
      <UiButton variant="ghost" :disabled="busy" @click="$emit('close')">取消</UiButton>
      <UiButton variant="danger" :disabled="busy" @click="$emit('confirm')">
        {{ busy ? "正在处理…" : confirmLabel }}
      </UiButton>
    </template>
  </BaseModal>
</template>
