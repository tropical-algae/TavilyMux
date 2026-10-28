import assert from "node:assert/strict"
import test from "node:test"

import { formatLatency, formatNumber, successRate } from "../src/utils/format.ts"

test("formats absent and present measurements", () => {
  assert.equal(formatNumber(null), "—")
  assert.equal(formatNumber(1234), "1,234")
  assert.equal(formatLatency(null), "—")
  assert.equal(formatLatency(42.6), "43 ms")
  assert.equal(formatLatency(1250), "1.25 s")
})

test("reports a request success rate", () => {
  assert.equal(successRate(0, 0), "—")
  assert.equal(successRate(3, 4), "75%")
})
