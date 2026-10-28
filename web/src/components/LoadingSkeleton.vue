<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 4 })
</script>

<template>
  <div class="skeleton" role="status" aria-label="正在加载">
    <span v-for="index in rows" :key="index" class="skeleton__line"></span>
  </div>
</template>
