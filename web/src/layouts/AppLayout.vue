<script setup lang="ts">
import {
  BookOpenText,
  ChevronRight,
  Command,
  LogOut,
  Network,
  Search,
  Settings,
  X,
} from "lucide-vue-next"
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"

import BrandLogo from "../components/BrandLogo.vue"
import WorkspacePreferences from "../components/WorkspacePreferences.vue"
import { useI18n } from "../i18n"
import { useAuthStore } from "../stores/auth"

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()
const commandOpen = ref(false)
const commandQuery = ref("")
const commandInput = ref<HTMLInputElement | null>(null)
const commandPalette = ref<HTMLElement | null>(null)
const commandPreviousFocus = ref<HTMLElement | null>(null)

const navigation = computed(() => [
  {
    to: "/",
    label: t("nav.pools"),
    shortLabel: t("nav.pools"),
    icon: Network,
    hint: t("nav.poolsHint"),
  },
  {
    to: "/logs",
    label: t("nav.logs"),
    shortLabel: t("nav.logsShort"),
    icon: BookOpenText,
    hint: t("nav.logsHint"),
  },
  {
    to: "/settings",
    label: t("nav.settings"),
    shortLabel: t("nav.settingsShort"),
    icon: Settings,
    hint: t("nav.settingsHint"),
  },
])

const currentPage = computed(() => {
  if (route.path.startsWith("/pools/")) return { label: t("layout.page.poolDetail") }
  return navigation.value.find((item) => item.to === route.path) ?? navigation.value[0]!
})

const commandResults = computed(() => {
  const query = commandQuery.value.trim().toLocaleLowerCase()
  if (!query) return navigation.value
  return navigation.value.filter((item) =>
    `${item.label} ${item.hint}`.toLocaleLowerCase().includes(query),
  )
})

async function logout(): Promise<void> {
  await auth.logout()
  await router.push("/login")
}

async function openCommand(): Promise<void> {
  if (commandOpen.value) return
  const activeElement = document.activeElement
  commandPreviousFocus.value =
    activeElement instanceof HTMLElement && activeElement !== document.body
      ? activeElement
      : null
  commandOpen.value = true
  await nextTick()
  commandInput.value?.focus()
}

function closeCommand(): void {
  if (!commandOpen.value) return
  const previousFocus = commandPreviousFocus.value
  commandOpen.value = false
  commandQuery.value = ""
  commandPreviousFocus.value = null
  void nextTick(() => previousFocus?.focus())
}

async function go(to: string): Promise<void> {
  closeCommand()
  await router.push(to)
}

function onGlobalKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null
  const isTyping = target?.matches("input, textarea, select, [contenteditable='true']")
  if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault()
    void openCommand()
    return
  }
  if (event.key === "/" && !isTyping && !commandOpen.value) {
    event.preventDefault()
    void openCommand()
    return
  }
  if (event.key === "Escape" && commandOpen.value) closeCommand()
}

function onCommandKeydown(event: KeyboardEvent): void {
  const palette = commandPalette.value
  if (!palette) return
  const focusable = Array.from(
    palette.querySelectorAll<HTMLElement>(
      'input, button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
    ),
  )
  if (focusable.length === 0) return

  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    const resultButtons = Array.from(
      palette.querySelectorAll<HTMLElement>(".command-palette__body button"),
    )
    if (resultButtons.length === 0) return
    event.preventDefault()
    const currentIndex = resultButtons.indexOf(document.activeElement as HTMLElement)
    const direction = event.key === "ArrowDown" ? 1 : -1
    const nextIndex =
      currentIndex === -1
        ? direction === 1
          ? 0
          : resultButtons.length - 1
        : (currentIndex + direction + resultButtons.length) % resultButtons.length
    resultButtons[nextIndex]?.focus()
    return
  }

  if (event.key === "Tab") {
    const first = focusable[0]
    const last = focusable.at(-1)
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }
}

watch(
  () => route.fullPath,
  () => closeCommand(),
)

onMounted(() => window.addEventListener("keydown", onGlobalKeydown))
onBeforeUnmount(() => window.removeEventListener("keydown", onGlobalKeydown))
</script>

<template>
  <div class="app-shell">
    <aside class="workspace-nav" :aria-label="t('layout.nav.main')">
      <RouterLink class="brand" to="/" :aria-label="t('layout.brandHome')">
        <BrandLogo class="brand__logo" />
        <span class="brand__name">TavilyMux</span>
      </RouterLink>

      <nav class="primary-nav">
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          :class="{ 'nav-home-link': item.to === '/' }"
          :exact-active-class="item.to === '/' ? 'router-link-exact-active' : undefined"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.8" />
          <strong>{{ item.label }}</strong>
          <ChevronRight :size="15" class="nav-chevron" aria-hidden="true" />
        </RouterLink>
      </nav>

      <div class="workspace-nav__footer">
        <div class="admin-chip" :aria-label="t('layout.adminCurrent')">
          <span class="admin-chip__avatar">
            A
            <span
              class="admin-chip__status"
              role="img"
              :aria-label="t('layout.serviceHealthy')"
              :title="t('layout.serviceHealthy')"
            ></span>
          </span>
          <span
            ><strong>Admin</strong><small>{{ t("common.admin") }}</small></span
          >
        </div>
        <button class="nav-action" type="button" @click="logout">
          <LogOut :size="17" />
          <span>{{ t("layout.logout") }}</span>
        </button>
      </div>
    </aside>

    <div class="workspace">
      <header class="workspace-bar">
        <RouterLink class="mobile-brand" to="/" :aria-label="t('layout.brandHome')">
          <BrandLogo class="brand__logo" :size="32" />
          <span>TavilyMux</span>
        </RouterLink>
        <div class="workspace-context">
          <strong>{{ currentPage.label }}</strong>
        </div>
        <div class="workspace-bar__tools">
          <button class="command-trigger" type="button" @click="openCommand">
            <Search :size="16" aria-hidden="true" />
            <span>{{ t("layout.command.search") }}</span>
            <kbd><Command :size="12" /> K</kbd>
          </button>
          <WorkspacePreferences />
        </div>
      </header>

      <main class="main-content">
        <RouterView v-slot="{ Component, route: renderedRoute }">
          <Transition name="page" mode="out-in">
            <component :is="Component" :key="renderedRoute.path" />
          </Transition>
        </RouterView>
      </main>

      <nav class="mobile-nav" :aria-label="t('layout.nav.mobile')">
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          :class="{ 'nav-home-link': item.to === '/' }"
          :exact-active-class="item.to === '/' ? 'router-link-exact-active' : undefined"
        >
          <component :is="item.icon" :size="20" :stroke-width="1.8" />
          <span>{{ item.shortLabel }}</span>
        </RouterLink>
      </nav>
    </div>

    <Transition name="overlay">
      <div v-if="commandOpen" class="command-overlay" @mousedown.self="closeCommand">
        <section
          ref="commandPalette"
          class="command-palette"
          role="dialog"
          aria-modal="true"
          :aria-label="t('layout.command.label')"
          @keydown="onCommandKeydown"
        >
          <div class="command-palette__search">
            <Search :size="19" aria-hidden="true" />
            <input
              ref="commandInput"
              v-model="commandQuery"
              type="search"
              autocomplete="off"
              :aria-label="t('layout.command.search')"
              :placeholder="t('layout.command.placeholder')"
            />
            <button type="button" :aria-label="t('layout.command.close')" @click="closeCommand">
              <X :size="17" />
            </button>
          </div>
          <div class="command-palette__body">
            <p>{{ t("layout.command.go") }}</p>
            <button
              v-for="item in commandResults"
              :key="item.to"
              type="button"
              @click="go(item.to)"
            >
              <span class="command-palette__icon"
                ><component :is="item.icon" :size="18"
              /></span>
              <span
                ><strong>{{ item.label }}</strong
                ><small>{{ item.hint }}</small></span
              >
              <ChevronRight :size="16" aria-hidden="true" />
            </button>
            <p v-if="commandResults.length === 0" class="command-palette__empty">
              {{ t("layout.command.empty") }}
            </p>
          </div>
          <footer>
            <span><kbd>↑</kbd><kbd>↓</kbd> {{ t("layout.command.browse") }}</span>
            <span
              ><kbd>Enter</kbd> {{ t("layout.command.open") }} · <kbd>Esc</kbd>
              {{ t("layout.command.close") }}</span
            >
          </footer>
        </section>
      </div>
    </Transition>
  </div>
</template>
