export type ThemePreference = "system" | "light" | "dark"
export type ResolvedTheme = "light" | "dark"

export function resolveTheme(value: ThemePreference, prefersDark: boolean): ResolvedTheme {
  return value === "system" ? (prefersDark ? "dark" : "light") : value
}
