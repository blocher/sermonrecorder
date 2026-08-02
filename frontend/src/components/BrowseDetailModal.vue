<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, X } from '@lucide/vue'

const props = defineProps<{
  open: boolean
  index: number
  count: number
  labelledBy: string
  closeLabel?: string
}>()

const emit = defineEmits<{
  close: []
  'update:index': [index: number]
}>()

const panel = ref<HTMLElement>()
const previousFocus = ref<HTMLElement | null>(null)

const positionLabel = computed(() => `${props.index + 1} of ${props.count}`)
const canGoPrevious = computed(() => props.index > 0)
const canGoNext = computed(() => props.index < props.count - 1)

function setBackgroundInert(inert: boolean): void {
  for (const selector of ['.app-header', '.app-content', '.record-control', '.share-shell']) {
    const element = document.querySelector<HTMLElement>(selector)
    element?.toggleAttribute('inert', inert)
    if (inert) element?.setAttribute('aria-hidden', 'true')
    else element?.removeAttribute('aria-hidden')
  }
}

function goPrevious(): void {
  if (!canGoPrevious.value) return
  emit('update:index', props.index - 1)
}

function goNext(): void {
  if (!canGoNext.value) return
  emit('update:index', props.index + 1)
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    goPrevious()
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    goNext()
  }
}

watch(
  () => props.open,
  async (open) => {
    document.body.classList.toggle('browse-detail-lock', open)
    setBackgroundInert(open)
    if (open) {
      previousFocus.value = document.activeElement as HTMLElement | null
      window.addEventListener('keydown', onKeydown)
      await nextTick()
      panel.value?.focus()
      return
    }
    window.removeEventListener('keydown', onKeydown)
    previousFocus.value?.focus?.()
    previousFocus.value = null
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.classList.remove('browse-detail-lock')
  setBackgroundInert(false)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="browse-detail"
      role="presentation"
      @click.self="emit('close')"
    >
      <div
        ref="panel"
        class="browse-detail__panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="labelledBy"
        tabindex="-1"
      >
        <header class="browse-detail__header">
          <p class="browse-detail__position" aria-live="polite">{{ positionLabel }}</p>
          <button
            type="button"
            class="browse-detail__close"
            :aria-label="closeLabel ?? 'Close'"
            @click="emit('close')"
          >
            <X :size="18" :stroke-width="1.8" aria-hidden="true" />
          </button>
        </header>

        <div class="browse-detail__body">
          <slot />
        </div>

        <footer v-if="count > 1" class="browse-detail__nav">
          <button
            type="button"
            class="browse-detail__nav-btn"
            :disabled="!canGoPrevious"
            aria-label="Previous item"
            @click="goPrevious"
          >
            <ChevronLeft :size="20" :stroke-width="1.8" aria-hidden="true" />
            Previous
          </button>
          <button
            type="button"
            class="browse-detail__nav-btn browse-detail__nav-btn--next"
            :disabled="!canGoNext"
            aria-label="Next item"
            @click="goNext"
          >
            Next
            <ChevronRight :size="20" :stroke-width="1.8" aria-hidden="true" />
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.browse-detail {
  background: color-mix(in srgb, var(--color-ink) 32%, transparent);
  bottom: 0;
  display: grid;
  left: 0;
  overflow: auto;
  padding: 0.75rem 0.75rem calc(1.25rem + env(safe-area-inset-bottom));
  place-items: center;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 60;
}

.browse-detail__panel {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  box-shadow: 0 22px 60px rgba(28, 36, 48, 0.24);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  margin: auto;
  max-height: min(40rem, calc(100svh - 1.5rem));
  max-width: 36rem;
  outline: none;
  width: min(100%, 36rem);
}

.browse-detail__header {
  align-items: center;
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.85rem 1rem 0.85rem 1.25rem;
}

.browse-detail__position {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

.browse-detail__close {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  cursor: pointer;
  display: inline-flex;
  justify-content: center;
  min-height: 2.25rem;
  min-width: 2.25rem;
  padding: 0;
}

.browse-detail__close:hover {
  border-color: var(--color-lapis);
  color: var(--color-lapis);
}

.browse-detail__close:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 2px;
}

.browse-detail__body {
  overflow: auto;
  overscroll-behavior: contain;
  padding: 1.25rem clamp(1.1rem, 3vw, 1.6rem) 1.5rem;
}

.browse-detail__nav {
  border-top: 1px solid var(--color-margin);
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
  padding: 0.75rem 1rem;
}

.browse-detail__nav-btn {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  gap: 0.2rem;
  letter-spacing: 0.04em;
  min-height: 2.5rem;
  padding: 0.35rem 0.4rem;
  text-transform: uppercase;
}

.browse-detail__nav-btn:disabled {
  color: var(--color-ink-muted);
  cursor: not-allowed;
  opacity: 0.45;
}

.browse-detail__nav-btn:not(:disabled):hover {
  color: var(--color-lapis-dark);
}

.browse-detail__nav-btn:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 2px;
}

.browse-detail__nav-btn--next {
  margin-left: auto;
}
</style>

<style>
body.browse-detail-lock {
  overflow: hidden;
}
</style>
