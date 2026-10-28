<script setup lang="ts">
import { ArrowUpRight, Search } from "lucide-vue-next"
import { computed } from "vue"
import { RouterLink } from "vue-router"

import type { Pool } from "../types/api"

const props = defineProps<{ pools: Pool[] }>()

const visiblePools = computed(() => props.pools.slice(0, 5))
const positions = computed(() => {
  const count = visiblePools.value.length
  if (count <= 1) return [160]
  return visiblePools.value.map((_, index) => 40 + (index / (count - 1)) * 240)
})

const mobilePositions = computed(() => {
  const count = visiblePools.value.length
  if (count === 0) return []
  const sourceHeight = 52
  const contentHeight = 404
  const gap = Math.max(8, (contentHeight - count * sourceHeight) / count)
  const firstCenter = 18 + gap / 2 + sourceHeight / 2
  return visiblePools.value.map((_, index) => firstCenter + index * (sourceHeight + gap))
})

function pathFor(index: number): string {
  const y = positions.value[index] ?? 160
  return `M 184 ${y} C 275 ${y}, 292 160, 386 160`
}

function mobilePathFor(index: number): string {
  const y = mobilePositions.value[index] ?? 155
  return `M 146 ${y} C 184 ${y}, 190 155, 228 155`
}
</script>

<template>
  <div class="routing-map" aria-label="账号池到 Tavily Search 的实时路由图">
    <svg
      class="routing-map__lines routing-map__lines--desktop"
      viewBox="0 0 760 320"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        v-for="(pool, index) in visiblePools"
        :key="pool.id"
        :d="pathFor(index)"
        :class="`route-line route-line--${pool.status}`"
      />
      <path class="route-line route-line--target" d="M 386 160 C 480 160, 500 160, 585 160" />
      <circle
        v-for="(pool, index) in visiblePools"
        :key="`${pool.id}-node`"
        cx="184"
        :cy="positions[index]"
        r="4"
        :class="`route-node route-node--${pool.status}`"
      />
      <circle class="route-node route-node--hub" cx="386" cy="160" r="5" />
      <circle class="route-node route-node--target" cx="585" cy="160" r="5" />
    </svg>
    <svg
      class="routing-map__lines routing-map__lines--mobile"
      viewBox="0 0 320 440"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        v-for="(pool, index) in visiblePools"
        :key="`${pool.id}-mobile-path`"
        :d="mobilePathFor(index)"
        :class="`route-line route-line--${pool.status}`"
      />
      <path class="route-line route-line--target" d="M 228 155 C 228 220, 228 260, 228 320" />
      <circle
        v-for="(pool, index) in visiblePools"
        :key="`${pool.id}-mobile-node`"
        cx="146"
        :cy="mobilePositions[index]"
        r="4"
        :class="`route-node route-node--${pool.status}`"
      />
      <circle class="route-node route-node--hub" cx="228" cy="155" r="5" />
      <circle class="route-node route-node--target" cx="228" cy="320" r="5" />
    </svg>

    <div class="routing-map__sources">
      <RouterLink
        v-for="pool in visiblePools"
        :key="pool.id"
        :to="`/pools/${pool.id}`"
        class="route-source"
      >
        <span
          class="route-source__signal"
          :class="`route-source__signal--${pool.status}`"
        ></span>
        <span
          ><strong>{{ pool.name }}</strong
          ><small>{{ pool.available_key_count }}/{{ pool.key_count }} Key 可用</small></span
        >
        <ArrowUpRight :size="14" aria-hidden="true" />
      </RouterLink>
    </div>

    <div class="route-hub" aria-hidden="true">
      <span class="route-hub__mark"><span></span><span></span><span></span></span>
      <strong>TavilyMux</strong>
      <small>额度感知路由</small>
    </div>

    <div class="route-destination" aria-hidden="true">
      <span><Search :size="18" /></span>
      <strong>Tavily Search</strong>
      <small>透明转发</small>
    </div>
  </div>
</template>
