import assert from "node:assert/strict"
import test from "node:test"

import {
  beginLoading,
  createLoadingLifecycle,
  remainingVisibleTime,
} from "../src/utils/loading.ts"

test("treats concurrent first-load requests as one lifecycle", () => {
  const lifecycle = createLoadingLifecycle()
  const finishFirst = beginLoading(lifecycle)
  const finishSecond = beginLoading(lifecycle)

  assert.deepEqual(lifecycle, { pendingCount: 2, initialized: false })
  finishFirst()
  assert.deepEqual(lifecycle, { pendingCount: 1, initialized: false })
  finishSecond()
  assert.deepEqual(lifecycle, { pendingCount: 0, initialized: true })
  finishSecond()
  assert.deepEqual(lifecycle, { pendingCount: 0, initialized: true })
})

test("calculates the remaining minimum skeleton duration", () => {
  assert.equal(remainingVisibleTime(180, 300, 320), 200)
  assert.equal(remainingVisibleTime(180, 600, 320), 0)
})
