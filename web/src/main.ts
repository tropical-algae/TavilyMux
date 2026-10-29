import { createPinia } from "pinia"
import { createApp } from "vue"

import App from "./App.vue"
import { initializeLocale } from "./i18n"
import router from "./router"
import "./styles/main.css"
import { initializeTheme } from "./theme"

initializeLocale()
initializeTheme()

createApp(App).use(createPinia()).use(router).mount("#app")
