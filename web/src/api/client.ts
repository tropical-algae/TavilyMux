import axios, { AxiosError } from "axios"

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30_000,
  withCredentials: true,
})

function cookie(name: string): string | undefined {
  const prefix = `${name}=`
  return document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix))
    ?.slice(prefix.length)
}

api.interceptors.request.use((config) => {
  if (config.method && !["get", "head", "options"].includes(config.method.toLowerCase())) {
    const token = cookie("tavily_mux_csrf")
    if (token) config.headers.set("X-CSRF-Token", decodeURIComponent(token))
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (error instanceof AxiosError && error.response?.status === 401) {
      const requestPath = error.config?.url ?? ""
      if (window.location.pathname !== "/login" && !requestPath.endsWith("/auth/login")) {
        const redirect = encodeURIComponent(
          `${window.location.pathname}${window.location.search}${window.location.hash}`,
        )
        window.location.assign(`/login?redirect=${redirect}`)
      }
    }
    return Promise.reject(error)
  },
)

export function errorMessage(error: unknown, fallback = "操作失败，请稍后重试"): string {
  if (!(error instanceof AxiosError)) return fallback
  const detail = error.response?.data?.detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail.error === "string") return detail.error
  if (error.code === "ECONNABORTED") return "请求超时，请检查连接设置后重试"
  return fallback
}
