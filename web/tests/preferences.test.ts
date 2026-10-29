import assert from "node:assert/strict"
import test from "node:test"

import { resolveLocale, translate } from "../src/i18n/index.ts"
import { resolveTheme } from "../src/theme/resolution.ts"

test("translates interface messages and interpolates values", () => {
  assert.equal(translate("zh-CN", "logs.page", { page: 3 }), "第 3 页")
  assert.equal(translate("en", "logs.page", { page: 3 }), "Page 3")
})

test("defaults to English unless a saved locale is available", () => {
  assert.equal(resolveLocale(null), "en")
  assert.equal(resolveLocale("invalid"), "en")
  assert.equal(resolveLocale("zh-CN"), "zh-CN")
})

test("resolves explicit and system theme preferences", () => {
  assert.equal(resolveTheme("system", true), "dark")
  assert.equal(resolveTheme("system", false), "light")
  assert.equal(resolveTheme("light", true), "light")
  assert.equal(resolveTheme("dark", false), "dark")
})
