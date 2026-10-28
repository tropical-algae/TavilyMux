import assert from "node:assert/strict"
import test from "node:test"

import {
  buildTimelineScale,
  sampleTimelineIndexes,
  scaleTimelineValue,
} from "../src/utils/timeline.ts"

test("scales quota changes to the visible data range", () => {
  const scale = buildTimelineScale([1000, 980])

  assert.deepEqual(scale, {
    minimum: 950,
    maximum: 1000,
    ticks: [1000, 975, 950],
  })
  assert.equal(scaleTimelineValue(1000, scale!, 12, 228), 12)
  assert.equal(scaleTimelineValue(950, scale!, 12, 228), 228)
})

test("keeps a useful range when quota values do not change", () => {
  assert.deepEqual(buildTimelineScale([1000, 1000]), {
    minimum: 950,
    maximum: 1000,
    ticks: [1000, 975, 950],
  })
})

test("samples timeline labels from first to last snapshot", () => {
  assert.deepEqual(sampleTimelineIndexes(12), [0, 4, 7, 11])
  assert.deepEqual(sampleTimelineIndexes(3), [0, 1, 2])
})
