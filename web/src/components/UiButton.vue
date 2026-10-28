<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost" | "danger"
    size?: "medium" | "small"
    type?: "button" | "submit" | "reset"
    disabled?: boolean
    block?: boolean
  }>(),
  {
    variant: "secondary",
    size: "medium",
    type: "button",
    disabled: false,
    block: false,
  },
)
</script>

<template>
  <button
    class="button"
    :class="[
      `button--${variant}`,
      { 'button--small': size === 'small', 'button--wide': block },
    ]"
    :type="type"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>
