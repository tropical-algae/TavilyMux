<script setup lang="ts">
import { AlertCircle, CheckCircle2, Info, X } from "lucide-vue-next"

import { useToastStore } from "../stores/toasts"

const toasts = useToastStore()
</script>

<template>
  <div class="toast-region" aria-live="polite" aria-atomic="false">
    <article
      v-for="toast in toasts.items"
      :key="toast.id"
      class="toast"
      :class="`toast--${toast.tone}`"
    >
      <CheckCircle2 v-if="toast.tone === 'success'" :size="18" aria-hidden="true" />
      <AlertCircle v-else-if="toast.tone === 'error'" :size="18" aria-hidden="true" />
      <Info v-else :size="18" aria-hidden="true" />
      <p>{{ toast.message }}</p>
      <button
        class="icon-button"
        type="button"
        aria-label="关闭提示"
        @click="toasts.dismiss(toast.id)"
      >
        <X :size="16" />
      </button>
    </article>
  </div>
</template>
