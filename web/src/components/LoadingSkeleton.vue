<script setup lang="ts">
import { useI18n } from "../i18n"

const { t } = useI18n()
withDefaults(defineProps<{ rows?: number }>(), { rows: 4 })
</script>

<template>
  <div class="skeleton" role="status" :aria-label="t('common.loading')">
    <span v-for="index in rows" :key="index" class="skeleton__line"></span>
  </div>
</template>
