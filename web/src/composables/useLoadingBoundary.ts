import { computed, reactive } from "vue"

import { beginLoading, createLoadingLifecycle } from "../utils/loading"
import { useDelayedSkeleton } from "./useDelayedSkeleton"

interface LoadingBoundaryOptions {
  delayMs?: number
  minimumVisibleMs?: number
  skeletonOnRefresh?: boolean
}

export function useLoadingBoundary(options: LoadingBoundaryOptions = {}) {
  const lifecycle = reactive(createLoadingLifecycle())
  const initialized = computed(() => lifecycle.initialized)
  const loading = computed(() => lifecycle.pendingCount > 0)
  const skeletonLoading = computed(
    () => loading.value && (options.skeletonOnRefresh || !initialized.value),
  )
  const showSkeleton = useDelayedSkeleton(skeletonLoading, options)

  async function run<T>(operation: () => Promise<T>): Promise<T> {
    const finish = beginLoading(lifecycle)
    try {
      return await operation()
    } finally {
      finish()
    }
  }

  return {
    initialized,
    loading,
    run,
    showSkeleton,
  }
}
