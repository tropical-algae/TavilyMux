<script setup lang="ts">
import { Trash2 } from "lucide-vue-next"
import { reactive, ref, watch } from "vue"

import type { Pool, RoutingStrategy } from "../types/api"
import SelectControl from "./SelectControl.vue"
import UiButton from "./UiButton.vue"

const props = defineProps<{ pool: Pool }>()
const emit = defineEmits<{
  save: [payload: Record<string, string | number | boolean | null>]
  delete: []
}>()

const routingOptions = [
  { value: "max_remaining", label: "剩余额度优先" },
  { value: "random", label: "随机可用 Key" },
]
const connectionOverride = ref(false)
const proxyTouched = reactive({ http: false, https: false })
const form = reactive({
  name: "",
  description: "",
  enabled: true,
  strategy: "max_remaining" as RoutingStrategy,
  monitor_interval_seconds: 300,
  max_attempts: 3,
  concurrency_limit: null as number | null,
  rpm_limit: null as number | null,
  upstream_base_url: "",
  http_proxy: "",
  https_proxy: "",
  allow_direct_fallback: false,
})

function sync(): void {
  Object.assign(form, {
    name: props.pool.name,
    description: props.pool.description ?? "",
    enabled: props.pool.enabled,
    strategy: props.pool.strategy,
    monitor_interval_seconds: props.pool.monitor_interval_seconds,
    max_attempts: props.pool.max_attempts,
    concurrency_limit: props.pool.concurrency_limit,
    rpm_limit: props.pool.rpm_limit,
    upstream_base_url: props.pool.upstream_base_url ?? "",
    http_proxy: "",
    https_proxy: "",
    allow_direct_fallback: props.pool.allow_direct_fallback ?? false,
  })
  connectionOverride.value = Boolean(
    props.pool.upstream_base_url ||
    props.pool.http_proxy ||
    props.pool.https_proxy ||
    props.pool.allow_direct_fallback !== null,
  )
  proxyTouched.http = false
  proxyTouched.https = false
}

function submit(): void {
  const payload: Record<string, string | number | boolean | null> = {
    name: form.name,
    description: form.description || null,
    enabled: form.enabled,
    strategy: form.strategy,
    monitor_interval_seconds: form.monitor_interval_seconds,
    max_attempts: form.max_attempts,
    concurrency_limit: form.concurrency_limit,
    rpm_limit: form.rpm_limit,
  }
  if (!connectionOverride.value) {
    Object.assign(payload, {
      upstream_base_url: null,
      http_proxy: null,
      https_proxy: null,
      allow_direct_fallback: null,
    })
  } else {
    payload.upstream_base_url = form.upstream_base_url || null
    payload.allow_direct_fallback = form.allow_direct_fallback
    if (proxyTouched.http) payload.http_proxy = form.http_proxy || null
    if (proxyTouched.https) payload.https_proxy = form.https_proxy || null
  }
  emit("save", payload)
}

function clearProxy(kind: "http" | "https"): void {
  form[`${kind}_proxy`] = ""
  proxyTouched[kind] = true
}

watch(() => props.pool, sync, { immediate: true })
</script>

<template>
  <form class="panel settings-form" @submit.prevent="submit">
    <div class="section-heading">
      <div>
        <h2>池级路由设置</h2>
        <p>保存后通过新的 Runtime 快照应用，不阻塞正在进行的请求。</p>
      </div>
    </div>
    <div class="form-grid">
      <label class="field"
        ><span>池名称</span><input v-model.trim="form.name" required
      /></label>
      <div class="field">
        <span>路由策略</span>
        <SelectControl v-model="form.strategy" :options="routingOptions" />
      </div>
      <label class="field field--span"
        ><span>描述</span><textarea v-model="form.description" rows="3" />
      </label>
      <label class="field"
        ><span>检测间隔（秒）</span
        ><input
          v-model.number="form.monitor_interval_seconds"
          type="number"
          min="60"
          max="86400"
      /></label>
      <label class="field"
        ><span>最大尝试次数</span
        ><input v-model.number="form.max_attempts" type="number" min="1" max="10"
      /></label>
      <label class="field"
        ><span>并发上限</span
        ><input
          v-model.number="form.concurrency_limit"
          type="number"
          min="1"
          placeholder="不限制"
      /></label>
      <label class="field"
        ><span>每分钟请求上限</span
        ><input v-model.number="form.rpm_limit" type="number" min="1" placeholder="不限制"
      /></label>
    </div>
    <label class="switch-field"
      ><input v-model="form.enabled" type="checkbox" /><span
        ><strong>启用账号池</strong><small>停用后所有中转凭证会立即停止路由。</small></span
      ></label
    >
    <div class="section-divider"></div>
    <div class="section-heading">
      <div>
        <h2>连接覆盖</h2>
        <p>默认继承全局 Tavily 地址和 Clash HTTP 代理；开启后仅影响这个池。</p>
      </div>
    </div>
    <label class="switch-field"
      ><input v-model="connectionOverride" type="checkbox" /><span
        ><strong>覆盖全局连接配置</strong
        ><small>关闭并保存会清除当前池的全部连接覆盖。</small></span
      ></label
    >
    <div v-if="connectionOverride" class="form-grid">
      <label class="field field--span"
        ><span>Tavily Base URL（留空继承全局）</span
        ><input
          v-model.trim="form.upstream_base_url"
          type="url"
          placeholder="https://api.tavily.com"
      /></label>
      <div class="field">
        <label for="pool-http-proxy">HTTP 代理</label>
        <input
          id="pool-http-proxy"
          v-model.trim="form.http_proxy"
          type="url"
          :placeholder="pool.http_proxy || 'http://127.0.0.1:7890'"
          @input="proxyTouched.http = true"
        />
        <small v-if="pool.http_proxy && !proxyTouched.http">当前：{{ pool.http_proxy }}</small>
        <button
          v-if="pool.http_proxy"
          class="field-action"
          type="button"
          @click="clearProxy('http')"
        >
          清除池级 HTTP 代理
        </button>
      </div>
      <div class="field">
        <label for="pool-https-proxy">HTTPS 代理</label>
        <input
          id="pool-https-proxy"
          v-model.trim="form.https_proxy"
          type="url"
          :placeholder="pool.https_proxy || 'http://127.0.0.1:7890'"
          @input="proxyTouched.https = true"
        />
        <small v-if="pool.https_proxy && !proxyTouched.https"
          >当前：{{ pool.https_proxy }}</small
        >
        <button
          v-if="pool.https_proxy"
          class="field-action"
          type="button"
          @click="clearProxy('https')"
        >
          清除池级 HTTPS 代理
        </button>
      </div>
      <label class="switch-field field--span"
        ><input v-model="form.allow_direct_fallback" type="checkbox" /><span
          ><strong>代理失败时允许直连</strong
          ><small>可能使流量绕过代理，默认建议关闭。</small></span
        ></label
      >
    </div>
    <div class="form-actions">
      <UiButton variant="danger" @click="emit('delete')">
        <Trash2 :size="16" />删除账号池
      </UiButton>
      <UiButton variant="primary" type="submit">保存池设置</UiButton>
    </div>
  </form>
</template>
