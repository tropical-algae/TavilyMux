<script setup lang="ts">
import { X } from "lucide-vue-next"
import { nextTick, onBeforeUnmount, ref, useId, useSlots, watch } from "vue"

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    size?: "small" | "medium" | "large"
    dismissible?: boolean
  }>(),
  {
    description: undefined,
    size: "medium",
    dismissible: true,
  },
)

const emit = defineEmits<{ close: [] }>()
const slots = useSlots()
const panel = ref<HTMLElement | null>(null)
const titleId = `modal-title-${useId()}`
const descriptionId = `modal-description-${useId()}`
let previousFocus: HTMLElement | null = null
let previousBodyOverflow = ""
let pageLocked = false

function focusableElements(): HTMLElement[] {
  return Array.from(
    panel.value?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    ) ?? [],
  ).filter((element) => !element.hasAttribute("aria-hidden"))
}

function requestClose(): void {
  if (props.dismissible) emit("close")
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault()
    requestClose()
    return
  }
  if (event.key !== "Tab") return

  const focusable = focusableElements()
  if (!focusable.length) {
    event.preventDefault()
    panel.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

function restorePage(): void {
  if (!pageLocked) return
  document.body.style.overflow = previousBodyOverflow
  pageLocked = false
  const target = previousFocus
  previousFocus = null
  void nextTick(() => target?.focus())
}

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      restorePage()
      return
    }
    previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    pageLocked = true
    await nextTick()
    const autofocus = panel.value?.querySelector<HTMLElement>("[autofocus]")
    const target = autofocus ?? focusableElements()[0] ?? panel.value
    target?.focus()
  },
  { flush: "post", immediate: true },
)

onBeforeUnmount(() => {
  if (props.open) restorePage()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-backdrop" @mousedown.self="requestClose">
        <section
          ref="panel"
          class="modal-panel"
          :class="`modal-panel--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="description ? descriptionId : undefined"
          tabindex="-1"
          @keydown="onKeydown"
        >
          <header class="modal-panel__header">
            <div>
              <h2 :id="titleId">{{ title }}</h2>
              <p v-if="description" :id="descriptionId">{{ description }}</p>
            </div>
            <button
              v-if="dismissible"
              class="icon-button"
              type="button"
              aria-label="关闭弹窗"
              @click="requestClose"
            >
              <X :size="18" />
            </button>
          </header>
          <div class="modal-panel__body"><slot /></div>
          <footer v-if="slots.footer" class="modal-panel__footer">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
