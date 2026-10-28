import { createRouter, createWebHistory } from "vue-router"

import AppLayout from "../layouts/AppLayout.vue"
import { useAuthStore } from "../stores/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: () => import("../views/LoginView.vue") },
    {
      path: "/",
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "dashboard", component: () => import("../views/DashboardView.vue") },
        {
          path: "pools/:id",
          name: "pool-detail",
          component: () => import("../views/PoolDetailView.vue"),
        },
        { path: "logs", name: "logs", component: () => import("../views/LogsView.vue") },
        {
          path: "settings",
          name: "settings",
          component: () => import("../views/SettingsView.vue"),
        },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) await auth.check()
  if (to.meta.requiresAuth && !auth.authenticated) {
    return { name: "login", query: { redirect: to.fullPath } }
  }
  if (to.name === "login" && auth.authenticated) return { name: "dashboard" }
  return true
})

export default router
