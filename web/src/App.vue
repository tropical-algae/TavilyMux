<script setup lang="ts">
import { computed } from "vue"
import { RouterView } from "vue-router"

import LoadingSkeleton from "./components/LoadingSkeleton.vue"
import ToastRegion from "./components/ToastRegion.vue"
import { useDelayedSkeleton } from "./composables/useDelayedSkeleton"
import { useAuthStore } from "./stores/auth"

const auth = useAuthStore()
const checkingSession = computed(() => !auth.checked)
const showSessionSkeleton = useDelayedSkeleton(checkingSession)
</script>

<template>
  <div v-if="showSessionSkeleton" class="app-bootstrap">
    <LoadingSkeleton :rows="6" />
  </div>
  <RouterView v-else-if="auth.checked" />
  <ToastRegion />
</template>
