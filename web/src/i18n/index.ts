import { readonly, ref } from "vue"

import { en, type MessageKey, zhCN } from "./messages.ts"

export type { MessageKey } from "./messages.ts"

export type Locale = "zh-CN" | "en"
type MessageParams = Record<string, string | number>

const STORAGE_KEY = "tavily-mux-locale"
const locale = ref<Locale>("en")

export function initializeLocale(): void {
  const runtime = browserRuntime()
  if (!runtime) return
  let stored: string | null = null
  try {
    stored = runtime.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Keep the English default when storage is unavailable.
  }
  locale.value = resolveLocale(stored)
  applyLocale()
}

export function setLocale(value: Locale): void {
  locale.value = value
  try {
    browserRuntime()?.localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // The in-memory preference still applies for this session.
  }
  applyLocale()
}

export function toggleLocale(): void {
  setLocale(locale.value === "zh-CN" ? "en" : "zh-CN")
}

export function t(key: MessageKey, params: MessageParams = {}): string {
  return translate(locale.value, key, params)
}

export function translate(
  targetLocale: Locale,
  key: MessageKey,
  params: MessageParams = {},
): string {
  const template = targetLocale === "en" ? en[key] : zhCN[key]
  return Object.entries(params).reduce(
    (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
    template,
  )
}

export function resolveLocale(stored: string | null): Locale {
  return stored === "zh-CN" || stored === "en" ? stored : "en"
}

export function currentLocale(): Locale {
  return locale.value
}

export function useI18n() {
  return {
    locale: readonly(locale),
    setLocale,
    t,
    toggleLocale,
  }
}

function applyLocale(): void {
  const document = (globalThis as { document?: { documentElement: { lang: string } } }).document
  if (document) document.documentElement.lang = locale.value
}

function browserRuntime(): {
  localStorage: {
    getItem(key: string): string | null
    setItem(key: string, value: string): void
  }
} | null {
  return (
    (
      globalThis as {
        window?: {
          localStorage: {
            getItem(key: string): string | null
            setItem(key: string, value: string): void
          }
        }
      }
    ).window ?? null
  )
}
