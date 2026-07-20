<script setup lang="ts">
import { computed } from 'vue'
import { Mic, Square } from '@lucide/vue'

const props = defineProps<{
  recording: boolean
  elapsedSeconds: number
}>()

const emit = defineEmits<{
  toggle: []
}>()

const elapsed = computed(() => {
  const minutes = Math.floor(props.elapsedSeconds / 60)
  const seconds = props.elapsedSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
</script>

<template>
  <div class="record-control" :class="{ 'record-control--active': recording }">
    <div v-if="recording" class="record-control__status" aria-live="polite">
      <span class="record-control__live">Recording</span>
      <span class="record-control__time">{{ elapsed }}</span>
      <span class="record-control__hint">Stored on this device</span>
    </div>

    <button
      class="record-seal"
      type="button"
      :aria-label="recording ? 'Stop recording' : 'Start recording'"
      :aria-pressed="recording"
      @click="emit('toggle')"
    >
      <span class="record-seal__beading" aria-hidden="true"></span>
      <span class="record-seal__field">
        <Square v-if="recording" :size="24" :stroke-width="1.9" fill="currentColor" />
        <Mic v-else :size="30" :stroke-width="1.65" />
      </span>
    </button>

    <span class="record-control__label">{{ recording ? 'Stop' : 'Record' }}</span>
  </div>
</template>

<style scoped>
.record-control {
  align-items: center;
  bottom: calc(var(--nav-height) + env(safe-area-inset-bottom) - 1rem);
  display: flex;
  flex-direction: column;
  position: fixed;
  right: max(1.25rem, calc((100vw - var(--page-width)) / 2 + 1.5rem));
  z-index: 40;
}

.record-control__status {
  align-items: center;
  background: var(--color-ink);
  border: 1px solid rgba(184, 150, 62, 0.55);
  border-radius: var(--radius-medium);
  box-shadow: 0 14px 35px rgba(28, 36, 48, 0.22);
  color: var(--color-vellum);
  display: grid;
  gap: 0.05rem 0.75rem;
  grid-template-columns: auto auto;
  margin-bottom: 0.75rem;
  min-width: 12.5rem;
  padding: 0.75rem 0.9rem;
}

.record-control__live {
  color: #f5a6b2;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.record-control__time {
  font-family: var(--font-utility);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  justify-self: end;
}

.record-control__hint {
  color: rgba(241, 238, 228, 0.66);
  font-family: var(--font-utility);
  font-size: 0.73rem;
  grid-column: 1 / -1;
}

.record-seal {
  align-items: center;
  appearance: none;
  background: var(--color-vellum-light);
  border: 2px solid var(--color-rule-gold);
  border-radius: 50%;
  box-shadow:
    0 0 0 4px var(--color-vellum),
    0 0 0 5px rgba(184, 150, 62, 0.45),
    0 9px 28px rgba(28, 36, 48, 0.2);
  color: var(--color-rubric);
  cursor: pointer;
  display: grid;
  height: 5rem;
  isolation: isolate;
  padding: 0;
  place-items: center;
  position: relative;
  transition:
    transform 180ms ease,
    background-color 180ms ease,
    color 180ms ease;
  width: 5rem;
}

.record-seal::before {
  border: 1px solid rgba(184, 150, 62, 0.66);
  border-radius: 50%;
  content: '';
  inset: 0.45rem;
  position: absolute;
}

.record-seal:hover {
  transform: translateY(-2px);
}

.record-seal:active {
  transform: scale(0.96);
}

.record-seal:focus-visible {
  outline: 3px solid var(--color-lapis);
  outline-offset: 7px;
}

.record-seal__beading {
  border: 1px dashed rgba(158, 27, 46, 0.5);
  border-radius: 50%;
  inset: 0.78rem;
  position: absolute;
}

.record-seal__field {
  align-items: center;
  display: flex;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.record-control--active .record-seal {
  animation: seal-breathe 2.2s ease-in-out infinite;
  background: var(--color-rubric);
  color: var(--color-vellum-light);
}

.record-control--active .record-seal__beading {
  border-color: rgba(241, 238, 228, 0.58);
}

.record-control__label {
  background: var(--color-vellum);
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  margin-top: 0.55rem;
  padding: 0 0.35rem;
  text-transform: uppercase;
}

@keyframes seal-breathe {
  0%,
  100% {
    box-shadow:
      0 0 0 4px var(--color-vellum),
      0 0 0 5px rgba(184, 150, 62, 0.5),
      0 9px 28px rgba(28, 36, 48, 0.2);
  }
  50% {
    box-shadow:
      0 0 0 4px var(--color-vellum),
      0 0 0 10px rgba(158, 27, 46, 0.13),
      0 12px 34px rgba(28, 36, 48, 0.24);
  }
}

@media (max-width: 640px) {
  .record-control {
    bottom: calc(var(--nav-height) + env(safe-area-inset-bottom) - 0.85rem);
    right: 1.1rem;
  }

  .record-seal {
    height: 4.5rem;
    width: 4.5rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .record-control--active .record-seal {
    animation: none;
  }

  .record-seal {
    transition: none;
  }
}
</style>
