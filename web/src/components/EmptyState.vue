<script setup lang="ts">
import { Orbit } from "lucide-vue-next"

defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="empty-state">
    <Orbit :size="28" :stroke-width="1.5" aria-hidden="true" />
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <slot />
  </div>
</template>
