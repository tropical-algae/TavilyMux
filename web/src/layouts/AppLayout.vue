<script setup lang="ts">
import {
  Activity,
  BookOpenText,
  KeyRound,
  LogOut,
  Menu,
  Network,
  Settings,
  X,
} from "lucide-vue-next"
import { ref } from "vue"
import { RouterLink, RouterView, useRouter } from "vue-router"

import { useAuthStore } from "../stores/auth"

const router = useRouter()
const auth = useAuthStore()
const menuOpen = ref(false)

const navigation = [
  { to: "/", label: "运行总览", icon: Activity },
  { to: "/pools", label: "账号池", icon: Network },
  { to: "/logs", label: "请求日志", icon: BookOpenText },
  { to: "/settings", label: "连接设置", icon: Settings },
]

async function logout(): Promise<void> {
  await auth.logout()
  await router.push("/login")
}
</script>

<template>
  <div class="app-shell">
    <header class="mobile-header">
      <RouterLink class="brand" to="/" aria-label="TavilyMux 首页">
        <span class="brand__mark"><KeyRound :size="20" /></span>
        <span>TavilyMux</span>
      </RouterLink>
      <button class="icon-button" type="button" aria-label="打开导航" @click="menuOpen = true">
        <Menu :size="22" />
      </button>
    </header>

    <button
      v-if="menuOpen"
      class="nav-backdrop"
      type="button"
      aria-label="关闭导航"
      @click="menuOpen = false"
    ></button>
    <aside class="sidebar" :class="{ 'sidebar--open': menuOpen }">
      <div class="sidebar__top">
        <RouterLink class="brand" to="/" aria-label="TavilyMux 首页" @click="menuOpen = false">
          <span class="brand__mark"><KeyRound :size="20" /></span>
          <span>TavilyMux</span>
        </RouterLink>
        <button
          class="icon-button sidebar__close"
          type="button"
          aria-label="关闭导航"
          @click="menuOpen = false"
        >
          <X :size="20" />
        </button>
      </div>

      <div class="system-signal">
        <span class="system-signal__pulse" aria-hidden="true"></span>
        <div>
          <strong>路由服务在线</strong>
          <span>单节点 · Runtime 就绪</span>
        </div>
      </div>

      <nav class="primary-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          :exact-active-class="item.to === '/' ? 'router-link-exact-active' : undefined"
          @click="menuOpen = false"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.8" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar__footer">
        <button class="nav-action" type="button" @click="logout">
          <LogOut :size="18" />
          <span>退出登录</span>
        </button>
        <span class="build-label">v0.1 · control deck</span>
      </div>
    </aside>

    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>
