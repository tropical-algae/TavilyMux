<script setup lang="ts">
import { Check, ChevronDown } from "lucide-vue-next"
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from "vue"

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    options: SelectOption[]
    placeholder?: string
    disabled?: boolean
    ariaLabel?: string
  }>(),
  {
    placeholder: "请选择",
    disabled: false,
    ariaLabel: undefined,
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
  change: [value: string]
}>()

const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const listboxId = `select-${useId()}`

const selectedOption = computed(() =>
  props.options.find((option) => option.value === props.modelValue),
)

function enabledOptions(): HTMLButtonElement[] {
  return Array.from(
    root.value?.querySelectorAll<HTMLButtonElement>("[role='option']:not(:disabled)") ?? [],
  )
}

function focusSelected(fallback: "first" | "last" = "first"): void {
  const options = enabledOptions()
  const selected = options.find((option) => option.dataset.value === props.modelValue)
  const target = selected ?? (fallback === "first" ? options[0] : options.at(-1))
  target?.focus()
}

function show(fallback: "first" | "last" = "first"): void {
  if (props.disabled) return
  open.value = true
  void nextTick(() => focusSelected(fallback))
}

function hide(restoreFocus = false): void {
  open.value = false
  if (restoreFocus) void nextTick(() => trigger.value?.focus())
}

function toggle(): void {
  if (open.value) hide()
  else show()
}

function select(option: SelectOption): void {
  if (option.disabled) return
  emit("update:modelValue", option.value)
  emit("change", option.value)
  hide(true)
}

function moveFocus(direction: 1 | -1): void {
  const options = enabledOptions()
  if (!options.length) return
  const current = options.indexOf(document.activeElement as HTMLButtonElement)
  const next = current < 0 ? (direction === 1 ? 0 : options.length - 1) : current + direction
  options[(next + options.length) % options.length]?.focus()
}

function onTriggerKeydown(event: KeyboardEvent): void {
  if (["ArrowDown", "ArrowUp"].includes(event.key)) {
    event.preventDefault()
    if (!open.value) show(event.key === "ArrowDown" ? "first" : "last")
    else moveFocus(event.key === "ArrowDown" ? 1 : -1)
    return
  }
  if (["Enter", " "].includes(event.key)) {
    event.preventDefault()
    toggle()
  } else if (event.key === "Escape" && open.value) {
    event.preventDefault()
    hide(true)
  }
}

function onOptionKeydown(event: KeyboardEvent, option: SelectOption): void {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault()
    moveFocus(event.key === "ArrowDown" ? 1 : -1)
  } else if (event.key === "Home" || event.key === "End") {
    event.preventDefault()
    enabledOptions()[event.key === "Home" ? 0 : enabledOptions().length - 1]?.focus()
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault()
    select(option)
  } else if (event.key === "Escape") {
    event.preventDefault()
    hide(true)
  } else if (event.key === "Tab") {
    hide()
  }
}

function onPointerDown(event: PointerEvent): void {
  if (!root.value?.contains(event.target as Node)) hide()
}

onMounted(() => window.addEventListener("pointerdown", onPointerDown))
onBeforeUnmount(() => window.removeEventListener("pointerdown", onPointerDown))
</script>

<template>
  <div ref="root" class="select-control" :class="{ 'select-control--open': open }">
    <button
      ref="trigger"
      class="select-control__trigger"
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      :aria-controls="listboxId"
      :aria-expanded="open"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span :class="{ 'select-control__placeholder': !selectedOption }">
        {{ selectedOption?.label ?? placeholder }}
      </span>
      <ChevronDown :size="16" aria-hidden="true" />
    </button>
    <div v-if="open" :id="listboxId" class="select-control__menu" role="listbox">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        role="option"
        :data-value="option.value"
        :aria-selected="option.value === modelValue"
        :disabled="option.disabled"
        @click="select(option)"
        @keydown="onOptionKeydown($event, option)"
      >
        <span>{{ option.label }}</span>
        <Check v-if="option.value === modelValue" :size="15" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>
