<script setup lang="ts">
import { ArrowRight, LockKeyhole } from "lucide-vue-next"
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { errorMessage } from "../api/client"
import UiButton from "../components/UiButton.vue"
import { useAuthStore } from "../stores/auth"

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const secret = ref("")
const remember = ref(false)
const loading = ref(false)
const error = ref("")

async function submit(): Promise<void> {
  error.value = ""
  loading.value = true
  try {
    await auth.login(secret.value, remember.value)
    const target = typeof route.query.redirect === "string" ? route.query.redirect : "/"
    await router.replace(target)
  } catch (cause) {
    error.value = errorMessage(cause, "管理密钥不正确，请检查后重试")
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-labelledby="login-title">
      <div class="login-brand" aria-label="TavilyMux">
        <img class="brand__logo" src="/tavily-mux.svg" alt="" width="34" height="34" />
        <span>TavilyMux</span>
      </div>
      <div>
        <h1 id="login-title">让每一次搜索，<br />抵达正确的位置。</h1>
        <p>统一管理账号池、额度和故障切换。搜索请求走内存路由，管理操作留在控制面。</p>
      </div>
      <div class="login-intro__signals" aria-label="产品能力">
        <span>透明转发</span>
        <span>自动切换</span>
        <span>额度观测</span>
      </div>
    </section>

    <section class="login-panel" aria-label="管理员登录">
      <div class="login-panel__heading">
        <LockKeyhole :size="22" aria-hidden="true" />
        <div>
          <h2>进入控制台</h2>
          <p>请输入部署时配置或首次启动生成的管理密钥。</p>
        </div>
      </div>

      <form @submit.prevent="submit">
        <label class="field">
          <span>管理密钥</span>
          <input
            v-model="secret"
            name="secret"
            type="password"
            autocomplete="current-password"
            placeholder="输入管理密钥"
            required
            autofocus
          />
        </label>
        <label class="check-field">
          <input v-model="remember" type="checkbox" />
          <span>在这台设备上保持登录</span>
        </label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <UiButton variant="primary" block type="submit" :disabled="loading || !secret">
          <span>{{ loading ? "正在验证…" : "进入控制台" }}</span>
          <ArrowRight v-if="!loading" :size="18" />
        </UiButton>
      </form>

      <p class="login-panel__note">管理密钥仅用于本服务控制台，不会发送给 Tavily。</p>
    </section>
  </main>
</template>
