import { computed, readonly, ref } from "vue"

import { type ResolvedTheme, resolveTheme, type ThemePreference } from "./resolution.ts"

export { resolveTheme, type ResolvedTheme, type ThemePreference } from "./resolution.ts"

const STORAGE_KEY = "tavily-mux-theme"
const preference = ref<ThemePreference>("system")
const systemDark = ref(false)
let mediaQuery: MediaQueryList | null = null

const resolvedTheme = computed<ResolvedTheme>(() =>
  resolveTheme(preference.value, systemDark.value),
)

export function initializeTheme(): void {
  if (typeof window === "undefined") return
  let stored: string | null = null
  try {
    stored = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Continue with the system preference when storage is unavailable.
  }
  preference.value = stored === "light" || stored === "dark" ? stored : "system"
  mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
  systemDark.value = mediaQuery.matches
  mediaQuery.addEventListener("change", onSystemThemeChange)
  applyTheme()
}

export function setTheme(value: ThemePreference): void {
  preference.value = value
  try {
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // The in-memory preference still applies for this session.
  }
  applyTheme()
}

export function useTheme() {
  return {
    preference: readonly(preference),
    resolvedTheme: readonly(resolvedTheme),
    setTheme,
  }
}

function onSystemThemeChange(event: MediaQueryListEvent): void {
  systemDark.value = event.matches
  if (preference.value === "system") applyTheme()
}

function applyTheme(): void {
  if (typeof document === "undefined") return
  const value = resolvedTheme.value
  document.documentElement.dataset.theme = value
  document.documentElement.style.colorScheme = value
  document
    .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    ?.setAttribute("content", value === "dark" ? "#191919" : "#ffffff")
  document
    .querySelector<HTMLLinkElement>("#app-icon")
    ?.setAttribute("href", value === "dark" ? "/tavily-mux-dark.svg" : "/tavily-mux.svg")
}
