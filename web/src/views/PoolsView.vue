<script setup lang="ts">
import { ArrowUpRight, Copy, Plus, X } from "lucide-vue-next"
import { computed, onMounted, reactive, ref } from "vue"
import { RouterLink } from "vue-router"

import { api, errorMessage } from "../api/client"
import EmptyState from "../components/EmptyState.vue"
import LoadingSkeleton from "../components/LoadingSkeleton.vue"
import PageHeader from "../components/PageHeader.vue"
import StatusBadge from "../components/StatusBadge.vue"
import { useToastStore } from "../stores/toasts"
import type { CreatedPool, Pool, RoutingStrategy } from "../types/api"
import { formatDate, formatNumber } from "../utils/format"

const pools = ref<Pool[]>([])
const loading = ref(true)
const saving = ref(false)
const createOpen = ref(false)
const error = ref("")
const created = ref<CreatedPool | null>(null)
const toasts = useToastStore()
const form = reactive({
  name: "",
  description: "",
  strategy: "max_remaining" as RoutingStrategy,
  monitor_interval_seconds: 300,
  max_attempts: 3,
  concurrency_limit: null as number | null,
  rpm_limit: null as number | null,
  connection_override: false,
  upstream_base_url: "",
  http_proxy: "",
  https_proxy: "",
  allow_direct_fallback: false,
})
const searchExample = computed(() => {
  if (!created.value) return ""
  return [
    `curl ${window.location.origin}/search \\`,
    `  -H 'Authorization: Bearer ${created.value.relay_key}' \\`,
    "  -H 'Content-Type: application/json' \\",
    `  -d '{"query":"hello from TavilyMux"}'`,
  ].join("\n")
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    pools.value = (await api.get<Pool[]>("/pools")).data
  } catch (cause) {
    error.value = errorMessage(cause, "账号池加载失败")
  } finally {
    loading.value = false
  }
}

async function createPool(): Promise<void> {
  saving.value = true
  error.value = ""
  try {
    const payload = {
      name: form.name,
      description: form.description || null,
      strategy: form.strategy,
      monitor_interval_seconds: form.monitor_interval_seconds,
      max_attempts: form.max_attempts,
      concurrency_limit: form.concurrency_limit,
      rpm_limit: form.rpm_limit,
      ...(form.connection_override
        ? {
            upstream_base_url: form.upstream_base_url || null,
            http_proxy: form.http_proxy || null,
            https_proxy: form.https_proxy || null,
            allow_direct_fallback: form.allow_direct_fallback,
          }
        : {}),
    }
    const response = await api.post<CreatedPool>("/pools", payload)
    created.value = response.data
    pools.value.unshift(response.data)
    createOpen.value = false
    form.name = ""
    form.description = ""
    form.connection_override = false
    form.upstream_base_url = ""
    form.http_proxy = ""
    form.https_proxy = ""
    form.allow_direct_fallback = false
    toasts.show("账号池已创建，请立即保存中转 Key", "success")
  } catch (cause) {
    error.value = errorMessage(cause, "账号池创建失败")
  } finally {
    saving.value = false
  }
}

async function copyKey(): Promise<void> {
  if (!created.value) return
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable")
    await navigator.clipboard.writeText(created.value.relay_key)
    toasts.show("中转 Key 已复制", "success")
  } catch {
    toasts.show("自动复制失败，请手动选择上方完整 Key", "error")
  }
}

onMounted(load)
</script>

<template>
  <div class="view-stack">
    <PageHeader title="账号池" description="每个池拥有独立路由策略、连接覆盖和中转凭证。">
      <template #actions>
        <button class="button button--primary" type="button" @click="createOpen = !createOpen">
          <X v-if="createOpen" :size="17" /><Plus v-else :size="17" />
          {{ createOpen ? "收起创建" : "创建账号池" }}
        </button>
      </template>
    </PageHeader>

    <section v-if="created" class="one-time-secret" aria-labelledby="secret-title">
      <div>
        <h2 id="secret-title">中转 Key 只显示这一次</h2>
        <p>请保存到调用方的安全配置中，关闭后无法再次查看完整值。</p>
      </div>
      <code>{{ created.relay_key }}</code>
      <div class="one-time-secret__actions">
        <button class="button button--primary" type="button" @click="copyKey">
          <Copy :size="16" />复制 Key
        </button>
        <button class="button button--ghost" type="button" @click="created = null">
          我已保存
        </button>
      </div>
    </section>
    <section v-if="created" class="relay-example" aria-label="Search 调用示例">
      <div>
        <strong>立即验证 /search</strong>
        <span>示例包含刚生成的完整中转 Key，关闭提示前请妥善保存。</span>
      </div>
      <pre><code>{{ searchExample }}</code></pre>
    </section>

    <Transition name="overlay">
      <div v-if="createOpen" class="sheet-overlay" @mousedown.self="createOpen = false">
        <form class="side-sheet form-panel" @submit.prevent="createPool">
          <div class="side-sheet__header">
            <div>
              <h2>创建账号池</h2>
              <p>先建立路由边界，Tavily Key 可以在创建后继续添加。</p>
            </div>
            <button
              class="icon-button"
              type="button"
              aria-label="关闭创建面板"
              @click="createOpen = false"
            >
              <X :size="18" />
            </button>
          </div>
          <div class="side-sheet__body">
            <div class="form-grid">
              <label class="field"
                ><span>池名称</span
                ><input
                  v-model.trim="form.name"
                  required
                  maxlength="100"
                  placeholder="例如：生产搜索"
              /></label>
              <label class="field"
                ><span>路由策略</span
                ><select v-model="form.strategy">
                  <option value="max_remaining">剩余额度优先</option>
                  <option value="random">随机可用 Key</option>
                </select></label
              >
              <label class="field field--span"
                ><span>描述（可选）</span
                ><textarea
                  v-model.trim="form.description"
                  rows="2"
                  placeholder="说明这个池服务的调用环境"
                />
              </label>
              <label class="field"
                ><span>额度检测间隔（秒）</span
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
                ><span>并发上限（可选）</span
                ><input
                  v-model.number="form.concurrency_limit"
                  type="number"
                  min="1"
                  placeholder="不限制"
              /></label>
              <label class="field"
                ><span>每分钟请求上限（可选）</span
                ><input
                  v-model.number="form.rpm_limit"
                  type="number"
                  min="1"
                  placeholder="不限制"
              /></label>
            </div>
            <label class="switch-field"
              ><input v-model="form.connection_override" type="checkbox" /><span
                ><strong>创建时覆盖全局连接</strong
                ><small>可以为这个池指定独立 Tavily 地址或 Clash HTTP 代理。</small></span
              ></label
            >
            <div v-if="form.connection_override" class="form-grid">
              <label class="field field--span"
                ><span>Tavily Base URL（留空继承全局）</span
                ><input
                  v-model.trim="form.upstream_base_url"
                  type="url"
                  placeholder="https://api.tavily.com"
              /></label>
              <label class="field"
                ><span>HTTP 代理</span
                ><input
                  v-model.trim="form.http_proxy"
                  type="url"
                  placeholder="http://127.0.0.1:7890"
              /></label>
              <label class="field"
                ><span>HTTPS 代理</span
                ><input
                  v-model.trim="form.https_proxy"
                  type="url"
                  placeholder="http://127.0.0.1:7890"
              /></label>
              <label class="switch-field field--span"
                ><input v-model="form.allow_direct_fallback" type="checkbox" /><span
                  ><strong>代理失败时允许直连</strong
                  ><small>可能绕过代理，默认关闭。</small></span
                ></label
              >
            </div>
            <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          </div>
          <div class="side-sheet__footer">
            <button class="button button--ghost" type="button" @click="createOpen = false">
              取消
            </button>
            <button
              class="button button--primary"
              type="submit"
              :disabled="saving || !form.name"
            >
              {{ saving ? "正在创建…" : "创建并生成中转 Key" }}
            </button>
          </div>
        </form>
      </div>
    </Transition>

    <LoadingSkeleton v-if="loading" :rows="6" />
    <div v-else-if="error && !createOpen" class="inline-error">
      <p>{{ error }}</p>
      <button class="button button--secondary" type="button" @click="load">重新加载</button>
    </div>
    <EmptyState
      v-else-if="pools.length === 0"
      title="建立第一条搜索航线"
      description="账号池把一组 Tavily Key 组合为一个稳定的中转入口。创建后系统会生成第一个中转 Key。"
    >
      <button class="button button--primary" type="button" @click="createOpen = true">
        创建账号池
      </button>
    </EmptyState>
    <section v-else class="pool-directory">
      <RouterLink
        v-for="pool in pools"
        :key="pool.id"
        :to="`/pools/${pool.id}`"
        class="pool-record"
      >
        <div class="pool-record__identity">
          <span
            class="pool-record__signal"
            :class="`pool-record__signal--${pool.status}`"
          ></span>
          <div>
            <strong>{{ pool.name }}</strong>
            <p>{{ pool.description || "未添加描述" }}</p>
            <small>最近使用：{{ formatDate(pool.last_used_at) }}</small>
          </div>
        </div>
        <StatusBadge :status="pool.status" />
        <div class="pool-record__metric">
          <span>可用 Key</span
          ><strong>{{ pool.available_key_count }} / {{ pool.key_count }}</strong>
        </div>
        <div class="pool-record__metric">
          <span>最高单 Key 可用</span
          ><strong>{{ formatNumber(pool.estimated_remaining) }}</strong>
        </div>
        <div class="pool-record__metric">
          <span>今日请求 / 成功率</span
          ><strong
            >{{ formatNumber(pool.requests_today) }} /
            {{ pool.success_rate_today.toFixed(1) }}%</strong
          >
        </div>
        <ArrowUpRight :size="18" aria-hidden="true" />
      </RouterLink>
    </section>
  </div>
</template>
