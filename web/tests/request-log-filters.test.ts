import assert from "node:assert/strict"
import test from "node:test"

import {
  countRequestLogFilters,
  createRequestLogFilters,
  parseRequestLogFilters,
  requestLogQueryMatches,
  serializeRequestLogFilters,
  toRequestLogApiParams,
} from "../src/utils/requestLogFilters.ts"

test("parses and normalizes request-log URL filters", () => {
  const filters = parseRequestLogFilters({
    pool_id: "pool-one",
    key_id: ["key-one", "ignored"],
    status_code: "429",
    success: "false",
    retried: "invalid",
    request_id: " request-123 ",
    time_from: "2026-10-28T09:30",
    time_to: "not-a-date",
    page: "3",
  })

  assert.deepEqual(filters, {
    pool_id: "pool-one",
    key_id: "key-one",
    status_code: "429",
    success: "false",
    retried: "",
    request_id: "request-123",
    time_from: "2026-10-28T09:30",
    time_to: "",
    page: 3,
    page_size: 50,
  })
})

test("drops a key filter that has no pool context", () => {
  const filters = parseRequestLogFilters({ key_id: "key-one" })

  assert.equal(filters.key_id, "")
})

test("serializes only active filters and non-default pagination", () => {
  const filters = {
    ...createRequestLogFilters(),
    pool_id: "pool-one",
    key_id: "key-one",
    success: "true" as const,
    page: 2,
  }

  assert.deepEqual(serializeRequestLogFilters(filters), {
    pool_id: "pool-one",
    key_id: "key-one",
    success: "true",
    page: "2",
  })
  assert.equal(requestLogQueryMatches(serializeRequestLogFilters(filters), filters), true)
  assert.equal(
    requestLogQueryMatches({ ...serializeRequestLogFilters(filters), stale: "1" }, filters),
    false,
  )
})

test("converts filters to typed API parameters", () => {
  const filters = {
    ...createRequestLogFilters(),
    pool_id: "pool-one",
    key_id: "key-one",
    status_code: "200",
    success: "true" as const,
    retried: "false" as const,
    request_id: "request-123",
    time_from: "2026-10-28T09:30",
  }

  assert.deepEqual(toRequestLogApiParams(filters), {
    page: 1,
    page_size: 50,
    pool_id: "pool-one",
    key_id: "key-one",
    status_code: 200,
    success: true,
    retried: false,
    request_id: "request-123",
    time_from: new Date("2026-10-28T09:30").toISOString(),
    time_to: undefined,
  })
  assert.equal(countRequestLogFilters(filters), 7)
})
