export interface LoadingLifecycle {
  pendingCount: number
  initialized: boolean
}

export function createLoadingLifecycle(): LoadingLifecycle {
  return { pendingCount: 0, initialized: false }
}

export function beginLoading(lifecycle: LoadingLifecycle): () => void {
  lifecycle.pendingCount += 1
  let finished = false

  return () => {
    if (finished) return
    finished = true
    lifecycle.pendingCount = Math.max(0, lifecycle.pendingCount - 1)
    if (lifecycle.pendingCount === 0) lifecycle.initialized = true
  }
}

export function remainingVisibleTime(
  shownAt: number,
  now: number,
  minimumVisibleMs: number,
): number {
  return Math.max(0, minimumVisibleMs - (now - shownAt))
}
