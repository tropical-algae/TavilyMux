<script setup lang="ts">
import { Cable, CheckCircle2, CircleAlert, Eye, EyeOff, Save, Shield } from "lucide-vue-next"
import { onMounted, reactive, ref } from "vue"

import { api, errorMessage } from "../api/client"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import UiButton from "../components/UiButton.vue"
import { useLoadingBoundary } from "../composables/useLoadingBoundary"
import { useI18n } from "../i18n"
import { useAuthStore } from "../stores/auth"
import { useToastStore } from "../stores/toasts"
import type { ConnectionTest, SystemSettings } from "../types/api"
import { formatLatency } from "../utils/format"

const settings = ref<SystemSettings | null>(null)
const { t } = useI18n()
const { initialized, run: runLoad, showSkeleton } = useLoadingBoundary()
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
  await runLoad(async () => {
    try {
      settings.value = (await api.get<SystemSettings>("/settings")).data
      Object.assign(form, {
        ...settings.value,
        http_proxy: "",
        https_proxy: "",
      })
      error.value = ""
    } catch (cause) {
      error.value = errorMessage(cause, t("settings.loadError"))
    }
  })
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
    toasts.show(t("settings.saved"), "success")
  } catch (cause) {
    error.value = errorMessage(cause, t("settings.saveError"))
  } finally {
    saving.value = false
  }
}

async function changeSecret(): Promise<void> {
  if (secretForm.new_secret !== secretForm.confirm) {
    toasts.show(t("settings.secretMismatch"), "error")
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
    toasts.show(errorMessage(cause, t("settings.secretUpdateError")), "error")
  }
}

async function testConnection(): Promise<void> {
  testing.value = true
  try {
    const result = (await api.post<ConnectionTest>("/settings/test")).data
    connectionResult.value = result
    const route = result.proxy_configured ? t("settings.proxyConfigured") : t("settings.direct")
    toasts.show(
      result.ok
        ? `${t("settings.connectionSuccess")} · ${route} · ${formatLatency(result.latency_ms)}`
        : `${t("settings.connectionFailed")} · ${formatLatency(result.latency_ms)}`,
      result.ok ? "success" : "error",
    )
  } catch (cause) {
    connectionResult.value = null
    toasts.show(errorMessage(cause, t("settings.connectionFailed")), "error")
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
      :title="t('settings.title')"
      :description="t('settings.connectionDescription')"
    />
    <LoadingSkeleton v-if="showSkeleton" :rows="7" />
    <div v-else-if="error && !settings" class="inline-error">
      <p>{{ error }}</p>
      <UiButton @click="load">{{ t("common.retry") }}</UiButton>
    </div>
    <template v-else-if="initialized">
      <form class="panel settings-form" @submit.prevent="save">
        <div class="section-heading section-heading--stack-mobile">
          <div>
            <h2>{{ t("settings.upstreamTitle") }}</h2>
            <p>{{ t("settings.proxyUrlHint") }}</p>
          </div>
          <UiButton :disabled="testing" @click="testConnection">
            <Cable :size="16" />{{
              testing ? t("settings.testRunning") : t("settings.connectionTest")
            }}
          </UiButton>
        </div>
        <label class="field"
          ><span>Tavily Base URL</span
          ><input
            v-model.trim="form.upstream_base_url"
            type="url"
            required
            placeholder="https://api.tavily.com"
          /><small>{{ t("settings.upstreamHint") }}</small></label
        >
        <div class="form-grid">
          <div class="field">
            <label for="global-http-proxy">{{ t("form.httpProxy") }}</label>
            <input
              id="global-http-proxy"
              v-model.trim="form.http_proxy"
              type="url"
              :placeholder="settings?.http_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.http = true"
            /><small v-if="settings?.http_proxy && !proxyTouched.http">{{
              t("common.current", { value: settings.http_proxy })
            }}</small
            ><button
              v-if="settings?.http_proxy"
              class="field-action"
              type="button"
              @click="clearProxy('http')"
            >
              {{ t("settings.clearProxy") }}
            </button>
          </div>
          <div class="field">
            <label for="global-https-proxy">{{ t("form.httpsProxy") }}</label>
            <input
              id="global-https-proxy"
              v-model.trim="form.https_proxy"
              type="url"
              :placeholder="settings?.https_proxy || 'http://127.0.0.1:7890'"
              @input="proxyTouched.https = true"
            /><small v-if="settings?.https_proxy && !proxyTouched.https">{{
              t("common.current", { value: settings.https_proxy })
            }}</small
            ><button
              v-if="settings?.https_proxy"
              class="field-action"
              type="button"
              @click="clearProxy('https')"
            >
              {{ t("settings.clearProxy") }}
            </button>
          </div>
        </div>
        <label class="switch-field switch-field--warning"
          ><input v-model="form.allow_direct_fallback" type="checkbox" /><span
            ><strong>{{ t("settings.allowDirect") }}</strong
            ><small>{{ t("settings.allowDirectHint") }}</small></span
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
            <strong>{{
              connectionResult.ok
                ? t("settings.connectionSuccess")
                : t("settings.connectionFailed")
            }}</strong>
            <span>
              {{
                connectionResult.proxy_configured
                  ? t("settings.proxyRoute")
                  : t("settings.direct")
              }}
              · {{ formatLatency(connectionResult.latency_ms) }} · HTTP
              {{ connectionResult.status_code ?? t("common.noResponse") }}
            </span>
          </div>
        </div>

        <div class="section-divider"></div>
        <div class="section-heading">
          <div>
            <h2>{{ t("settings.runtimeTitle") }}</h2>
            <p>{{ t("settings.runtimeDescription") }}</p>
          </div>
        </div>
        <div class="form-grid form-grid--four">
          <label class="field"
            ><span>{{ t("form.monitorInterval") }}</span
            ><input
              v-model.number="form.monitor_interval_seconds"
              type="number"
              min="60"
              max="86400" /></label
          ><label class="field"
            ><span>{{ t("settings.requestTimeout") }}</span
            ><input
              v-model.number="form.request_timeout_seconds"
              type="number"
              min="1"
              max="600" /></label
          ><label class="field"
            ><span>{{ t("form.maxAttempts") }}</span
            ><input v-model.number="form.max_attempts" type="number" min="1" max="10" /></label
          ><label class="field"
            ><span>{{ t("settings.logRetention") }}</span
            ><input v-model.number="form.log_retention_days" type="number" min="1" max="3650"
          /></label>
        </div>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="form-actions">
          <UiButton variant="primary" type="submit" :disabled="saving">
            <Save :size="17" />{{ saving ? t("settings.saving") : t("settings.save") }}
          </UiButton>
        </div>
      </form>

      <form class="panel settings-form" @submit.prevent="changeSecret">
        <div class="section-heading">
          <div>
            <h2>{{ t("settings.adminKey") }}</h2>
            <p>{{ t("settings.adminKeyHint") }}</p>
          </div>
          <Shield :size="22" aria-hidden="true" />
        </div>
        <div class="form-grid form-grid--three">
          <label class="field"
            ><span>{{ t("settings.currentKey") }}</span
            ><input
              v-model="secretForm.current_secret"
              :type="secretVisible ? 'text' : 'password'"
              required
              autocomplete="current-password" /></label
          ><label class="field"
            ><span>{{ t("settings.newKey") }}</span
            ><input
              v-model="secretForm.new_secret"
              :type="secretVisible ? 'text' : 'password'"
              required
              minlength="12"
              autocomplete="new-password" /></label
          ><label class="field"
            ><span>{{ t("settings.newKeyConfirm") }}</span
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
          /><span>{{
            secretVisible ? t("settings.hideKey") : t("settings.showKey")
          }}</span></label
        >
        <div class="form-actions">
          <UiButton type="submit">{{ t("settings.adminKeyChanged") }}</UiButton>
        </div>
      </form>
    </template>
  </div>
</template>
