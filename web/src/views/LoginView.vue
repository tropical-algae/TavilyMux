<script setup lang="ts">
import { ArrowRight, LockKeyhole } from "lucide-vue-next"
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { errorMessage } from "../api/client"
import BrandLogo from "../components/BrandLogo.vue"
import UiButton from "../components/UiButton.vue"
import { useI18n } from "../i18n"
import { useAuthStore } from "../stores/auth"

const auth = useAuthStore()
const { t } = useI18n()
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
    error.value = errorMessage(cause, t("login.error"))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-labelledby="login-title">
      <div class="login-brand" aria-label="TavilyMux">
        <BrandLogo class="brand__logo" />
        <span>TavilyMux</span>
      </div>
      <div>
        <h1 id="login-title" v-html="t('login.titleHtml')"></h1>
        <p>{{ t("login.lead") }}</p>
      </div>
      <div class="login-intro__signals" :aria-label="t('login.features')">
        <span>{{ t("login.featureRelay") }}</span>
        <span>{{ t("login.featureFailover") }}</span>
        <span>{{ t("login.featureQuota") }}</span>
      </div>
    </section>

    <section class="login-panel" :aria-label="t('login.aria')">
      <div class="login-panel__heading">
        <LockKeyhole :size="22" aria-hidden="true" />
        <div>
          <h2>{{ t("login.signIn") }}</h2>
          <p>{{ t("login.subtitle") }}</p>
        </div>
      </div>

      <form @submit.prevent="submit">
        <label class="field">
          <span>{{ t("login.key") }}</span>
          <input
            v-model="secret"
            name="secret"
            type="password"
            autocomplete="current-password"
            :placeholder="t('login.keyPlaceholder')"
            required
            autofocus
          />
        </label>
        <label class="check-field">
          <input v-model="remember" type="checkbox" />
          <span>{{ t("login.keepSignedIn") }}</span>
        </label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <UiButton variant="primary" block type="submit" :disabled="loading || !secret">
          <span>{{ loading ? t("login.signingIn") : t("login.signIn") }}</span>
          <ArrowRight v-if="!loading" :size="18" />
        </UiButton>
      </form>

      <p class="login-panel__note">{{ t("login.keyHint") }}</p>
    </section>
  </main>
</template>
