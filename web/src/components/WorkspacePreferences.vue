<script setup lang="ts">
import { Check, ChevronDown, Languages, Monitor, Moon, Sun } from "lucide-vue-next"
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

import { useI18n } from "../i18n"
import { type ThemePreference, useTheme } from "../theme"

const { locale, t, toggleLocale } = useI18n()
const { preference, resolvedTheme, setTheme } = useTheme()
const root = ref<HTMLElement | null>(null)
const themeOpen = ref(false)

const languageLabel = computed(() => (locale.value === "zh-CN" ? "中文" : "EN"))
const themeIcon = computed(() =>
  preference.value === "system" ? Monitor : resolvedTheme.value === "dark" ? Moon : Sun,
)
const themeOptions = computed(() => [
  { value: "system" as const, label: t("preferences.themeSystem"), icon: Monitor },
  { value: "light" as const, label: t("preferences.themeLight"), icon: Sun },
  { value: "dark" as const, label: t("preferences.themeDark"), icon: Moon },
])

function chooseTheme(value: ThemePreference): void {
  setTheme(value)
  themeOpen.value = false
}

function onPointerDown(event: PointerEvent): void {
  if (!root.value?.contains(event.target as Node)) themeOpen.value = false
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") themeOpen.value = false
}

onMounted(() => {
  window.addEventListener("pointerdown", onPointerDown)
  window.addEventListener("keydown", onKeydown)
})
onBeforeUnmount(() => {
  window.removeEventListener("pointerdown", onPointerDown)
  window.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <div ref="root" class="workspace-preferences">
    <button
      class="preference-control"
      type="button"
      :aria-label="t('preferences.languageSwitch')"
      :title="t('preferences.languageSwitch')"
      @click="toggleLocale"
    >
      <Languages :size="16" aria-hidden="true" />
      <span>{{ languageLabel }}</span>
    </button>

    <div class="theme-picker">
      <button
        class="preference-control"
        type="button"
        aria-haspopup="menu"
        :aria-expanded="themeOpen"
        :aria-label="t('preferences.themeTitle')"
        :title="t('preferences.themeTitle')"
        @click="themeOpen = !themeOpen"
      >
        <component :is="themeIcon" :size="16" aria-hidden="true" />
        <span>{{ t("preferences.theme") }}</span>
        <ChevronDown :size="13" aria-hidden="true" />
      </button>
      <Transition name="select-menu">
        <div v-if="themeOpen" class="theme-menu" role="menu">
          <p>{{ t("preferences.themeTitle") }}</p>
          <button
            v-for="option in themeOptions"
            :key="option.value"
            type="button"
            role="menuitemradio"
            :aria-checked="preference === option.value"
            @click="chooseTheme(option.value)"
          >
            <component :is="option.icon" :size="16" aria-hidden="true" />
            <span>{{ option.label }}</span>
            <Check v-if="preference === option.value" :size="15" aria-hidden="true" />
          </button>
        </div>
      </Transition>
    </div>
  </div>
</template>
