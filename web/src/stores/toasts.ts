import { defineStore } from "pinia"
import { ref } from "vue"

export type ToastTone = "success" | "error" | "info"

export interface Toast {
  id: number
  message: string
  tone: ToastTone
}

export const useToastStore = defineStore("toasts", () => {
  const items = ref<Toast[]>([])
  let nextId = 1

  function show(message: string, tone: ToastTone = "info"): void {
    const id = nextId++
    items.value.push({ id, message, tone })
    window.setTimeout(() => dismiss(id), 4000)
  }

  function dismiss(id: number): void {
    items.value = items.value.filter((item) => item.id !== id)
  }

  return { items, show, dismiss }
})
