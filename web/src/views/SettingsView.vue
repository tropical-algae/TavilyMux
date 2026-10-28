<script setup lang="ts">
import { Cable, CheckCircle2, CircleAlert, Eye, EyeOff, Save, Shield } from "lucide-vue-next"
import { onMounted, reactive, ref } from "vue"

import { api, errorMessage } from "../api/client"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import { useDelayedSkeleton } from "../composables/useDelayedSkeleton"
import { useAuthStore } from "../stores/auth"
import { useToastStore } from "../stores/toasts"
import type { ConnectionTest, SystemSettings } from "../types/api"
import { formatLatency } from "../utils/format"

const settings = ref<SystemSettings | null>(null)
const loading = ref(true)
const showSkeleton = useDelayedSkeleton(loading)
const saving = ref(false)
const testing = ref(false)
const connectionResult = ref<ConnectionTest | null>(null)
const error = ref("")
const proxyTouched = reactive({ http: false, https: false })
const form = reactive({
  upstream_base_url: "",
  http_proxy: "",
  https_proxy: "",
  allow_direct_fallback: false,
  monitor_interval_seconds: 300,
  request_timeout_seconds: 60,
  max_attempts: 3,
  log_retention_days: 30,
})
const secretForm = reactive({ current_secret: "", new_secret: "", confirm: "" })
const secretVisible = ref(false)
const toasts = useToastStore()
const auth = useAuthStore()

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    settings.value = (await api.get<SystemSettings>("/settings")).data
    Object.assign(form, {
      ...settings.value,
      http_proxy: "",
      https_proxy: "",
    })
  } catch (cause) {
    error.value = errorMessage(cause, "设置加载失败")
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  error.value = ""
  const payload: Record<string, string | number | boolean | null> = {
    upstream_base_url: form.upstream_base_url,
    allow_direct_fallback: form.allow_direct_fallback,
    monitor_interval_seconds: form.monitor_interval_seconds,
    request_timeout_seconds: form.request_timeout_seconds,
    max_attempts: form.max_attempts,
    log_retention_days: form.log_retention_days,
  }
  if (proxyTouched.http) payload.http_proxy = form.http_proxy || null
  if (proxyTouched.https) payload.https_proxy = form.https_proxy || null
  try {
    settings.value = (await api.patch<SystemSettings>("/settings", payload)).data
    proxyTouched.http = false
    proxyTouched.https = false
    form.http_proxy = ""
    form.https_proxy = ""
    toasts.show("连接与运行设置已保存", "success")
  } catch (cause) {
    error.value = errorMessage(cause, "设置保存失败，请检查地址格式")
  } finally {
    saving.value = false
  }
}

async function changeSecret(): Promise<void> {
  if (secretForm.new_secret !== secretForm.confirm) {
    toasts.show("两次输入的新密钥不一致", "error")
    return
  }
  try {
    await api.put("/auth/secret", {
      current_secret: secretForm.current_secret,
      new_secret: secretForm.new_secret,
    })
    auth.authenticated = false
    window.location.assign("/login")
  } catch (cause) {
    toasts.show(errorMessage(cause, "管理密钥修改失败"), "error")
  }
}

async function testConnection(): Promise<void> {
  testing.value = true
  try {
    const result = (await api.post<ConnectionTest>("/settings/test")).data
    connectionResult.value = result
    const route = result.proxy_configured ? "已配置代理" : "直连"
    toasts.show(
      result.ok
        ? `${result.message} · ${route} · ${formatLatency(result.latency_ms)}`
        : `${result.message} · ${formatLatency(result.latency_ms)}`,
      result.ok ? "success" : "error",
    )
  } catch (cause) {
    connectionResult.value = null
    toasts.show(errorMessage(cause, "连接测试失败"), "error")
  } finally {
    testing.value = false
  }
}

function clearProxy(kind: "http" | "https"): void {
  form[`${kind}_proxy`] = ""
  proxyTouched[kind] = true
}

onMounted(load)
</script>

<template>
  <div class="view-stack">
    <PageHeader
      title="连接设置"
      description="配置服务访问 Tavily 时使用的地址、Clash HTTP 代理和运行参数。"
    />
    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error && !settings" class="inline-error">
      <p>{{ error }}</p>
      <button class="button button--secondary" @click="load">重新加载</button>
    </div>
    <template v-else>
      <form class="panel settings-form" @submit.prevent="save">
        <div class="section-heading">
          <div>
            <h2>上游连接</h2>
            <p>代理地址是 Clash 等服务暴露的 HTTP URL，不是 VPN 配置文件。</p>
          </div>
          <button
            class="button button--secondary"
            type="button"
            :disabled="testing"
            @click="testConnection"
          >
            <Cable :size="16" />{{ testing ? "正在测试…" : "测试已保存连接" }}
          </button>
        </div>
        <label class="field"
          ><span>Tavily Base URL</span
          ><input
            v-model.trim="form.upstream_base_url"
            type="url"
            required
            placeholder="https://api.tavily.com"
          /><small>搜索请求会原样转发到这个地址下的 /search。</small></label
        >
        <div class="form-grid">
          <div class="field">
            <label for="global-http-proxy">HTTP 代理</label>
            <input
              id="global-http-proxy"
              v-model.trim="form.http_proxy"
              type="url"
              :placeholder="settings?.http_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.http = true"
            /><small v-if="settings?.http_proxy && !proxyTouched.http"
              >当前：{{ settings.http_proxy }}</small
            ><button
              v-if="settings?.http_proxy"
              class="field-action"
              type="button"
              @click="clearProxy('http')"
            >
              清除已保存代理
            </button>
          </div>
          <div class="field">
            <label for="global-https-proxy">HTTPS 代理</label>
            <input
              id="global-https-proxy"
              v-model.trim="form.https_proxy"
              type="url"
              :placeholder="settings?.https_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.https = true"
            /><small v-if="settings?.https_proxy && !proxyTouched.https"
              >当前：{{ settings.https_proxy }}</small
            ><button
              v-if="settings?.https_proxy"
              class="field-action"
              type="button"
              @click="clearProxy('https')"
            >
              清除已保存代理
            </button>
          </div>
        </div>
        <label class="switch-field switch-field--warning"
          ><input v-model="form.allow_direct_fallback" type="checkbox" /><span
            ><strong>代理失败时允许直连</strong
            ><small>默认关闭。开启后代理连接失败可能使流量绕过代理。</small></span
          ></label
        >
        <div
          v-if="connectionResult"
          class="connection-result"
          :class="{ 'connection-result--error': !connectionResult.ok }"
          role="status"
        >
          <component :is="connectionResult.ok ? CheckCircle2 : CircleAlert" :size="19" />
          <div>
            <strong>{{ connectionResult.message }}</strong>
            <span>
              {{ connectionResult.proxy_configured ? "经已配置代理" : "直连" }} ·
              {{ formatLatency(connectionResult.latency_ms) }} · HTTP
              {{ connectionResult.status_code ?? "未响应" }}
            </span>
          </div>
        </div>

        <div class="section-divider"></div>
        <div class="section-heading">
          <div>
            <h2>运行参数</h2>
            <p>全局默认值可被单个账号池覆盖。</p>
          </div>
        </div>
        <div class="form-grid form-grid--four">
          <label class="field"
            ><span>检测间隔（秒）</span
            ><input
              v-model.number="form.monitor_interval_seconds"
              type="number"
              min="60"
              max="86400" /></label
          ><label class="field"
            ><span>请求超时（秒）</span
            ><input
              v-model.number="form.request_timeout_seconds"
              type="number"
              min="1"
              max="600" /></label
          ><label class="field"
            ><span>最大尝试次数</span
            ><input v-model.number="form.max_attempts" type="number" min="1" max="10" /></label
          ><label class="field"
            ><span>日志保留（天）</span
            ><input v-model.number="form.log_retention_days" type="number" min="1" max="3650"
          /></label>
        </div>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="form-actions">
          <button class="button button--primary" type="submit" :disabled="saving">
            <Save :size="17" />{{ saving ? "正在保存…" : "保存并应用" }}
          </button>
        </div>
      </form>

      <form class="panel settings-form" @submit.prevent="changeSecret">
        <div class="section-heading">
          <div>
            <h2>管理密钥</h2>
            <p>修改后所有现有登录会话立即失效。</p>
          </div>
          <Shield :size="22" aria-hidden="true" />
        </div>
        <div class="form-grid form-grid--three">
          <label class="field"
            ><span>当前管理密钥</span
            ><input
              v-model="secretForm.current_secret"
              :type="secretVisible ? 'text' : 'password'"
              required
              autocomplete="current-password" /></label
          ><label class="field"
            ><span>新管理密钥</span
            ><input
              v-model="secretForm.new_secret"
              :type="secretVisible ? 'text' : 'password'"
              required
              minlength="12"
              autocomplete="new-password" /></label
          ><label class="field"
            ><span>确认新密钥</span
            ><input
              v-model="secretForm.confirm"
              :type="secretVisible ? 'text' : 'password'"
              required
              minlength="12"
              autocomplete="new-password"
          /></label>
        </div>
        <label class="check-field"
          ><input v-model="secretVisible" type="checkbox" /><component
            :is="secretVisible ? EyeOff : Eye"
            :size="15"
          /><span>{{ secretVisible ? "隐藏密钥" : "显示密钥" }}</span></label
        >
        <div class="form-actions">
          <button class="button button--secondary" type="submit">修改管理密钥</button>
        </div>
      </form>
    </template>
  </div>
</template>
