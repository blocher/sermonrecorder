<script setup lang="ts">
withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  {
    compact: false,
  },
)
</script>

<template>
  <div class="brand-mark" :class="{ 'brand-mark--compact': compact }" aria-label="Pewcorder, AI Sermon Journal">
    <span class="brand-mark__name">Pewcorder</span>
    <span v-if="!compact" class="brand-mark__descriptor">AI Sermon Journal</span>
  </div>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1;
}

.brand-mark__name {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-variation-settings: 'opsz' 48, 'SOFT' 55, 'WONK' 0;
  font-weight: 620;
  letter-spacing: -0.045em;
}

.brand-mark__descriptor {
  color: var(--color-rubric);
  font-family: var(--font-utility);
  font-size: 0.625rem;
  font-weight: 650;
  letter-spacing: 0.17em;
  margin-top: 0.35rem;
  text-transform: uppercase;
}

.brand-mark--compact .brand-mark__name {
  font-size: 1.55rem;
}
</style>
