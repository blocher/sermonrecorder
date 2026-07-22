<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { LoaderCircle, Mic, Square } from '@lucide/vue'
import type { RecorderState } from '../recording/useDraftRecorder'

const props = defineProps<{
  state: RecorderState
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

const recording = computed(() => props.state === 'recording')
const busy = computed(() => props.state === 'requesting' || props.state === 'saving')
const immersive = computed(() => props.state !== 'idle' && props.state !== 'error')
const label = computed(() => {
  if (props.state === 'recording') return 'Stop'
  if (props.state === 'requesting') return 'Starting…'
  if (props.state === 'saving') return 'Saving…'
  return 'Record'
})
const statusLabel = computed(() => {
  if (props.state === 'recording') return 'Recording'
  if (props.state === 'requesting') return 'Microphone'
  return 'Saving'
})
const statusHint = computed(() => {
  if (props.state === 'recording') return 'Recording locally on this device'
  if (props.state === 'requesting') return 'Allow access to begin recording'
  return 'Saving the Draft on this device — longer recordings take a moment'
})
const statusTime = computed(() => {
  if (props.state === 'recording') return elapsed.value
  if (props.state === 'requesting') return 'Waiting'
  return 'Local'
})

watch(
  immersive,
  (active) => {
    document.body.classList.toggle('recording-lock', active)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.body.classList.remove('recording-lock')
})
</script>

<template>
  <div
    v-if="immersive"
    class="record-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="record-overlay-title"
  >
    <p id="record-overlay-title" class="rubric-label record-overlay__rubric">{{ statusLabel }}</p>
    <p class="record-overlay__time" aria-live="polite">{{ statusTime }}</p>
    <p class="record-overlay__hint">{{ statusHint }}</p>

    <button
      class="record-seal record-seal--overlay"
      type="button"
      :aria-label="recording ? 'Stop recording' : 'Start recording'"
      :aria-pressed="recording"
      :aria-busy="busy"
      :disabled="busy && !recording"
      @click="emit('toggle')"
    >
      <span class="record-seal__beading" aria-hidden="true"></span>
      <span class="record-seal__field">
        <Square v-if="recording" :size="28" :stroke-width="1.9" fill="currentColor" />
        <LoaderCircle v-else class="record-seal__spinner" :size="30" :stroke-width="1.65" />
      </span>
    </button>
    <span class="record-overlay__label">{{ label }}</span>
  </div>

  <div v-else class="record-control">
    <button
      class="record-seal"
      type="button"
      aria-label="Start recording"
      aria-pressed="false"
      @click="emit('toggle')"
    >
      <span class="record-seal__beading" aria-hidden="true"></span>
      <span class="record-seal__field">
        <Mic :size="30" :stroke-width="1.65" />
      </span>
    </button>
    <span class="record-control__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.record-overlay {
  align-items: center;
  background:
    radial-gradient(ellipse at 50% 28%, rgba(158, 27, 46, 0.14), transparent 52%),
    var(--color-vellum);
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  left: 0;
  padding: 2rem 1.5rem calc(2rem + env(safe-area-inset-bottom));
  position: fixed;
  right: 0;
  top: 0;
  z-index: 80;
}

.record-overlay__rubric {
  margin-bottom: 0.75rem;
}

.record-overlay__time {
  font-family: var(--font-display);
  font-size: clamp(4.5rem, 18vw, 7.5rem);
  font-variant-numeric: tabular-nums;
  font-variation-settings: 'opsz' 96, 'SOFT' 40;
  font-weight: 500;
  letter-spacing: -0.04em;
  line-height: 0.9;
  margin: 0;
}

.record-overlay__hint {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.95rem;
  margin: 1.25rem 0 3rem;
  text-align: center;
}

.record-overlay__label {
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  margin-top: 1rem;
  text-transform: uppercase;
}

.record-control {
  align-items: center;
  bottom: calc(1.35rem + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  position: fixed;
  right: max(1.25rem, calc((100vw - var(--page-width)) / 2 + 1.5rem));
  z-index: 40;
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

.record-seal:disabled {
  cursor: wait;
  opacity: 0.82;
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

.record-seal--overlay {
  animation: seal-breathe 2.2s ease-in-out infinite;
  background: var(--color-rubric);
  color: var(--color-vellum-light);
  height: 5.75rem;
  width: 5.75rem;
}

.record-seal--overlay .record-seal__beading {
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

.record-seal__spinner {
  animation: seal-spin 900ms linear infinite;
}

@keyframes seal-spin {
  to {
    transform: rotate(360deg);
  }
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
    backdrop-filter: blur(14px);
    background: color-mix(in srgb, var(--color-vellum) 94%, transparent);
    border-top: 1px solid var(--color-margin);
    bottom: 0;
    box-shadow: 0 -8px 24px rgba(28, 36, 48, 0.08);
    flex-direction: row;
    justify-content: center;
    left: 0;
    padding: 0.5rem 1rem calc(0.5rem + env(safe-area-inset-bottom));
    right: 0;
  }

  .record-seal {
    box-shadow:
      0 0 0 3px var(--color-vellum),
      0 0 0 4px rgba(184, 150, 62, 0.45),
      0 6px 18px rgba(28, 36, 48, 0.16);
    height: 3.5rem;
    width: 3.5rem;
  }

  .record-seal::before {
    inset: 0.32rem;
  }

  .record-seal__beading {
    inset: 0.56rem;
  }

  .record-seal__field :deep(svg) {
    height: 1.45rem;
    width: 1.45rem;
  }

  .record-control__label {
    margin: 0 0 0 0.8rem;
  }

  .record-seal--overlay {
    height: 5.25rem;
    width: 5.25rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .record-seal--overlay {
    animation: none;
  }

  .record-seal {
    transition: none;
  }

  .record-seal__spinner {
    animation: none;
  }
}
</style>
