<script setup lang="ts">
import { computed } from "vue"

import { useTheme } from "../theme"

const props = withDefaults(
  defineProps<{
    size?: number
    alt?: string
  }>(),
  {
    size: 34,
    alt: "",
  },
)

const { resolvedTheme } = useTheme()
const source = computed(() =>
  resolvedTheme.value === "dark" ? "/tavily-mux-dark.svg" : "/tavily-mux.svg",
)
</script>

<template>
  <img :src="source" :alt="alt" :width="props.size" :height="props.size" />
</template>
