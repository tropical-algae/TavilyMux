<script setup lang="ts">
import { CalendarDays } from "lucide-vue-next"
import { computed, ref } from "vue"

const props = withDefaults(
  defineProps<{
    modelValue: string
    id?: string
    disabled?: boolean
    ariaLabel?: string
  }>(),
  {
    id: undefined,
    disabled: false,
    ariaLabel: undefined,
  },
)

const emit = defineEmits<{ "update:modelValue": [value: string] }>()
const input = ref<HTMLInputElement | null>(null)
const displayValue = computed(() => {
  if (!props.modelValue) return "选择日期与时间"
  const [date, time = ""] = props.modelValue.split("T")
  return `${date?.replaceAll("-", "/")} ${time}`.trim()
})

function update(event: Event): void {
  emit("update:modelValue", (event.target as HTMLInputElement).value)
}

function showPicker(): void {
  if (!input.value) return
  try {
    if (typeof input.value.showPicker === "function") input.value.showPicker()
    else input.value.click()
  } catch {
    input.value.focus()
  }
}
</script>

<template>
  <div class="datetime-control">
    <input
      :id="id"
      ref="input"
      type="datetime-local"
      :value="modelValue"
      :disabled="disabled"
      :aria-label="ariaLabel || '日期与时间值'"
      aria-hidden="true"
      tabindex="-1"
      @input="update"
    />
    <button
      class="datetime-control__trigger"
      type="button"
      :aria-label="ariaLabel || '选择日期与时间'"
      :disabled="disabled"
      @click="showPicker"
    >
      <span :class="{ 'datetime-control__placeholder': !modelValue }">{{ displayValue }}</span>
      <CalendarDays :size="16" aria-hidden="true" />
    </button>
  </div>
</template>
