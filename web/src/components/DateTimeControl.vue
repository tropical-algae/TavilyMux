<script setup lang="ts">
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-vue-next"
import { computed, ref } from "vue"

import { currentLocale, useI18n } from "../i18n"
import BaseModal from "./BaseModal.vue"
import SelectControl from "./SelectControl.vue"
import UiButton from "./UiButton.vue"

const { t } = useI18n()

interface CalendarCell {
  key: string
  year: number
  month: number
  day: number
  currentMonth: boolean
  today: boolean
}

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
const open = ref(false)
const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth())
const selectedYear = ref(viewYear.value)
const selectedMonth = ref(viewMonth.value)
const selectedDay = ref(now.getDate())
const draftHour = ref("00")
const draftMinute = ref("00")
const weekdays = computed(() => t("datetime.weekdays").split(","))

const hourOptions = Array.from({ length: 24 }, (_, hour) => {
  const value = String(hour).padStart(2, "0")
  return { value, label: value }
})
const minuteOptions = Array.from({ length: 60 }, (_, minute) => {
  const value = String(minute).padStart(2, "0")
  return { value, label: value }
})

const displayValue = computed(() => {
  if (!props.modelValue) return t("datetime.choose")
  return new Intl.DateTimeFormat(currentLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(props.modelValue))
})

const monthLabel = computed(() =>
  t("datetime.month", { year: viewYear.value, month: viewMonth.value + 1 }),
)

const calendarDays = computed<CalendarCell[]>(() => {
  const today = new Date()
  const firstDay = new Date(viewYear.value, viewMonth.value, 1)
  const mondayOffset = (firstDay.getDay() + 6) % 7
  const start = new Date(viewYear.value, viewMonth.value, 1 - mondayOffset)
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index)
    return {
      key: `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`,
      year: date.getFullYear(),
      month: date.getMonth(),
      day: date.getDate(),
      currentMonth: date.getMonth() === viewMonth.value,
      today:
        date.getFullYear() === today.getFullYear() &&
        date.getMonth() === today.getMonth() &&
        date.getDate() === today.getDate(),
    }
  })
})

function parseValue(): void {
  const match = props.modelValue.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  const current = new Date()
  selectedYear.value = match ? Number(match[1]) : current.getFullYear()
  selectedMonth.value = match ? Number(match[2]) - 1 : current.getMonth()
  selectedDay.value = match ? Number(match[3]) : current.getDate()
  draftHour.value = match?.[4] ?? String(current.getHours()).padStart(2, "0")
  draftMinute.value = match?.[5] ?? String(current.getMinutes()).padStart(2, "0")
  viewYear.value = selectedYear.value
  viewMonth.value = selectedMonth.value
}

function openPicker(): void {
  if (props.disabled) return
  parseValue()
  open.value = true
}

function changeMonth(delta: number): void {
  const date = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function selectDay(cell: CalendarCell): void {
  selectedYear.value = cell.year
  selectedMonth.value = cell.month
  selectedDay.value = cell.day
  viewYear.value = cell.year
  viewMonth.value = cell.month
}

function selectToday(): void {
  const today = new Date()
  selectDay({
    key: "today",
    year: today.getFullYear(),
    month: today.getMonth(),
    day: today.getDate(),
    currentMonth: true,
    today: true,
  })
}

function isSelected(cell: CalendarCell): boolean {
  return (
    cell.year === selectedYear.value &&
    cell.month === selectedMonth.value &&
    cell.day === selectedDay.value
  )
}

function confirm(): void {
  const year = String(selectedYear.value).padStart(4, "0")
  const month = String(selectedMonth.value + 1).padStart(2, "0")
  const day = String(selectedDay.value).padStart(2, "0")
  emit("update:modelValue", `${year}-${month}-${day}T${draftHour.value}:${draftMinute.value}`)
  open.value = false
}

function clear(): void {
  emit("update:modelValue", "")
  open.value = false
}
</script>

<template>
  <div class="datetime-control">
    <button
      :id="id"
      class="datetime-control__trigger"
      type="button"
      :aria-label="ariaLabel || t('datetime.choose')"
      :disabled="disabled"
      @click="openPicker"
    >
      <span :class="{ 'datetime-control__placeholder': !modelValue }">{{ displayValue }}</span>
      <CalendarDays :size="16" aria-hidden="true" />
    </button>

    <BaseModal
      :open="open"
      :title="ariaLabel || t('datetime.choose')"
      :description="t('datetime.description')"
      size="small"
      @close="open = false"
    >
      <div class="date-picker">
        <div class="date-picker__toolbar">
          <button
            type="button"
            :aria-label="t('datetime.previousMonth')"
            @click="changeMonth(-1)"
          >
            <ChevronLeft :size="17" />
          </button>
          <strong>{{ monthLabel }}</strong>
          <button type="button" :aria-label="t('datetime.nextMonth')" @click="changeMonth(1)">
            <ChevronRight :size="17" />
          </button>
        </div>
        <div class="date-picker__weekdays" aria-hidden="true">
          <span v-for="weekday in weekdays" :key="weekday">{{ weekday }}</span>
        </div>
        <div class="date-picker__days" role="grid" :aria-label="monthLabel">
          <button
            v-for="cell in calendarDays"
            :key="cell.key"
            type="button"
            role="gridcell"
            :class="{
              'date-picker__day--muted': !cell.currentMonth,
              'date-picker__day--today': cell.today,
              'date-picker__day--selected': isSelected(cell),
            }"
            :aria-selected="isSelected(cell)"
            :aria-label="
              t('datetime.dateAria', { year: cell.year, month: cell.month + 1, day: cell.day })
            "
            @click="selectDay(cell)"
          >
            {{ cell.day }}
          </button>
        </div>
        <div class="date-picker__time">
          <span>{{ t("datetime.time") }}</span>
          <div>
            <SelectControl
              v-model="draftHour"
              :options="hourOptions"
              :aria-label="t('datetime.hours')"
            />
            <strong>:</strong>
            <SelectControl
              v-model="draftMinute"
              :options="minuteOptions"
              :aria-label="t('datetime.minutes')"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="clear">{{ t("common.clear") }}</UiButton>
        <UiButton @click="selectToday">{{ t("datetime.today") }}</UiButton>
        <UiButton variant="primary" @click="confirm">{{ t("common.confirm") }}</UiButton>
      </template>
    </BaseModal>
  </div>
</template>
