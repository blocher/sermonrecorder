<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { UserRound } from '@lucide/vue'
import AppNavigation from './components/AppNavigation.vue'
import BrandMark from './components/BrandMark.vue'
import RecordSeal from './components/RecordSeal.vue'
import { useDraftRecorder } from './recording/useDraftRecorder'

const route = useRoute()
const publicRoute = computed(() => route.meta.public === true)
const draftSaved = ref(false)
const {
  state,
  elapsedSeconds,
  drafts,
  errorMessage,
  lastSavedDraft,
  hasPendingRecording,
  initialize,
  toggle,
  retrySave,
  clearError,
} = useDraftRecorder()

const draftStatus = computed(() => {
  if (drafts.value.length === 0) return 'No drafts on device'
  return `${drafts.value.length} ${drafts.value.length === 1 ? 'draft' : 'drafts'} on device`
})

watch(lastSavedDraft, (draft) => {
  if (!draft) return
  draftSaved.value = true
  window.setTimeout(() => {
    draftSaved.value = false
  }, 3200)
})

onMounted(initialize)
</script>

<template>
  <RouterView v-if="publicRoute" />

  <div v-else class="app-shell">
    <header class="app-header">
      <div class="app-header__inner">
        <RouterLink class="app-header__brand" to="/" aria-label="Pewcorder library">
          <BrandMark compact />
        </RouterLink>
        <span class="app-header__status">{{ draftStatus }}</span>
        <button class="app-header__account" type="button" aria-label="Open account">
          <UserRound :size="20" :stroke-width="1.6" aria-hidden="true" />
        </button>
      </div>
    </header>

    <div v-if="draftSaved" class="draft-saved" role="status">
      <strong>Draft saved on this device.</strong>
      Add details or upload when you are ready.
    </div>

    <aside v-if="state === 'error'" class="recording-error" role="alert">
      <div>
        <strong>Recording needs attention</strong>
        <span>{{ errorMessage }}</span>
      </div>
      <button v-if="hasPendingRecording" type="button" @click="retrySave">Try saving again</button>
      <button v-else type="button" @click="clearError">Dismiss</button>
    </aside>

    <RouterView />
    <RecordSeal :state="state" :elapsed-seconds="elapsedSeconds" @toggle="toggle" />
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

.recording-error {
  align-items: center;
  background: var(--color-vellum-light);
  border: 1px solid var(--color-rubric);
  box-shadow: 0 12px 32px rgba(28, 36, 48, 0.16);
  display: flex;
  gap: 1.25rem;
  justify-content: space-between;
  left: 50%;
  max-width: min(36rem, calc(100vw - 2rem));
  padding: 0.9rem 1rem;
  position: fixed;
  top: calc(var(--header-height) + 1rem);
  transform: translateX(-50%);
  width: 100%;
  z-index: 50;
}

.recording-error strong,
.recording-error span {
  display: block;
  font-family: var(--font-utility);
}

.recording-error strong {
  color: var(--color-rubric);
  font-size: 0.78rem;
}

.recording-error span {
  color: var(--color-ink-muted);
  font-size: 0.76rem;
  line-height: 1.4;
  margin-top: 0.15rem;
}

.recording-error button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  flex: none;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
  padding: 0.6rem;
  text-decoration: underline;
  text-underline-offset: 0.2rem;
}

@media (max-width: 520px) {
  .app-header__status {
    display: none;
  }

  .recording-error {
    align-items: start;
    flex-direction: column;
    gap: 0.4rem;
  }

  .recording-error button {
    padding: 0.2rem 0;
  }
}
</style>
