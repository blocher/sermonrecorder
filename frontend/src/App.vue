<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { UserRound } from '@lucide/vue'
import AppNavigation from './components/AppNavigation.vue'
import BrandMark from './components/BrandMark.vue'
import RecordSeal from './components/RecordSeal.vue'

const route = useRoute()
const publicRoute = computed(() => route.meta.public === true)
const recording = ref(false)
const elapsedSeconds = ref(0)
const draftSaved = ref(false)
let timer: number | undefined

function toggleRecording() {
  if (recording.value) {
    recording.value = false
    draftSaved.value = true
    window.setTimeout(() => {
      draftSaved.value = false
    }, 2800)
    return
  }

  elapsedSeconds.value = 0
  recording.value = true
}

watch(recording, (isRecording) => {
  if (isRecording) {
    timer = window.setInterval(() => {
      elapsedSeconds.value += 1
    }, 1000)
  } else if (timer) {
    window.clearInterval(timer)
  }
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <RouterView v-if="publicRoute" />

  <div v-else class="app-shell">
    <header class="app-header">
      <div class="app-header__inner">
        <RouterLink class="app-header__brand" to="/" aria-label="Pewcorder library">
          <BrandMark compact />
        </RouterLink>
        <span class="app-header__status">1 draft on device</span>
        <button class="app-header__account" type="button" aria-label="Open account">
          <UserRound :size="20" :stroke-width="1.6" aria-hidden="true" />
        </button>
      </div>
    </header>

    <div v-if="draftSaved" class="draft-saved" role="status">
      <strong>Draft saved on this device.</strong>
      Add details or upload when you are ready.
    </div>

    <RouterView />
    <RecordSeal :recording="recording" :elapsed-seconds="elapsedSeconds" @toggle="toggleRecording" />
    <AppNavigation />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100svh;
  padding-top: var(--header-height);
}

.app-header {
  background: color-mix(in srgb, var(--color-vellum) 95%, transparent);
  border-bottom: 1px solid var(--color-margin);
  height: var(--header-height);
  left: 0;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 30;
}

.app-header__inner {
  align-items: center;
  display: grid;
  grid-template-columns: 1fr auto auto;
  height: 100%;
  margin: 0 auto;
  max-width: var(--page-width);
  padding: 0 clamp(1.25rem, 4vw, 3rem);
}

.app-header__brand {
  justify-self: start;
  text-decoration: none;
}

.app-header__status {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  margin-right: 1.2rem;
}

.app-header__account {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-rule-gold);
  border-radius: 50%;
  color: var(--color-ink);
  cursor: pointer;
  display: flex;
  height: 2.6rem;
  justify-content: center;
  width: 2.6rem;
}

.app-header__account:hover,
.app-header__account:focus-visible {
  border-color: var(--color-lapis);
  color: var(--color-lapis);
}

.app-header__account:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 3px;
}

.draft-saved {
  background: var(--color-lapis);
  box-shadow: 0 8px 24px rgba(28, 36, 48, 0.18);
  color: var(--color-vellum-light);
  font-family: var(--font-utility);
  font-size: 0.8rem;
  left: 50%;
  max-width: calc(100vw - 2rem);
  padding: 0.85rem 1.1rem;
  position: fixed;
  top: calc(var(--header-height) + 1rem);
  transform: translateX(-50%);
  z-index: 50;
}

.draft-saved strong {
  margin-right: 0.25rem;
}

@media (max-width: 520px) {
  .app-header__status {
    display: none;
  }
}
</style>
