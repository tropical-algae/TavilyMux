import { onScopeDispose, readonly, ref, watch, type Ref } from "vue"

import { SKELETON_TIMING } from "../config/experience"
import { remainingVisibleTime } from "../utils/loading"

interface SkeletonTiming {
  delayMs?: number
  minimumVisibleMs?: number
}

export function useDelayedSkeleton(loading: Ref<boolean>, timing: SkeletonTiming = {}) {
  const delayMs = timing.delayMs ?? SKELETON_TIMING.delayMs
  const minimumVisibleMs = timing.minimumVisibleMs ?? SKELETON_TIMING.minimumVisibleMs
  const visible = ref(false)
  let shownAt = 0
  let showTimer: ReturnType<typeof setTimeout> | undefined
  let hideTimer: ReturnType<typeof setTimeout> | undefined

  function clearTimers(): void {
    if (showTimer) clearTimeout(showTimer)
    if (hideTimer) clearTimeout(hideTimer)
    showTimer = undefined
    hideTimer = undefined
  }

  watch(
    loading,
    (isLoading) => {
      if (showTimer) clearTimeout(showTimer)
      showTimer = undefined

      if (isLoading) {
        if (hideTimer) clearTimeout(hideTimer)
        hideTimer = undefined
        if (visible.value) return
        showTimer = setTimeout(() => {
          visible.value = true
          shownAt = Date.now()
          showTimer = undefined
        }, delayMs)
        return
      }

      if (!visible.value) return
      const remaining = remainingVisibleTime(shownAt, Date.now(), minimumVisibleMs)
      hideTimer = setTimeout(() => {
        visible.value = false
        hideTimer = undefined
      }, remaining)
    },
    { immediate: true },
  )

  onScopeDispose(clearTimers)
  return readonly(visible)
}
