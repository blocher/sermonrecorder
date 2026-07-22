<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, UserRound } from '@lucide/vue'
import { useAuth } from './auth/useAuth'
import BrandMark from './components/BrandMark.vue'
import DraftWizard from './components/DraftWizard.vue'
import RecordSeal from './components/RecordSeal.vue'
import {
  initializeProcessingAlerts,
  syncProcessingAlerts,
} from './notifications/useProcessingAlerts'
import { useDraftRecorder } from './recording/useDraftRecorder'

const route = useRoute()
const router = useRouter()
const publicRoute = computed(() => route.meta.public === true)
const { isAuthenticated } = useAuth()
const {
  state,
  elapsedSeconds,
  drafts,
  errorMessage,
  wizardDraftId,
  hasPendingRecording,
  initialize,
  toggle,
  retrySave,
  clearError,
  closeDraftWizard,
} = useDraftRecorder()

const draftStatus = computed(() => {
  if (drafts.value.length === 0) return 'No drafts on device'
  return `${drafts.value.length} ${drafts.value.length === 1 ? 'draft' : 'drafts'} on device`
})

const searchActive = computed(() => route.path === '/' && route.query.focus === 'search')
const modalActive = computed(
  () =>
    searchActive.value ||
    Boolean(wizardDraftId.value) ||
    (state.value !== 'idle' && state.value !== 'error'),
)

function openSearch(): void {
  if (route.path === '/' && route.query.focus === 'search') return
  void router.push({ path: '/', query: { focus: 'search' } })
}

function onWizardUploaded(sermonId: string): void {
  closeDraftWizard()
  void router.push(`/sermons/${encodeURIComponent(sermonId)}`)
}

watch(isAuthenticated, (authenticated) => {
  if (authenticated) void syncProcessingAlerts()
})

onMounted(() => {
  void initialize()
  void initializeProcessingAlerts((sermonId) => {
    void router.push(`/sermons/${encodeURIComponent(sermonId)}`)
  })
  if (isAuthenticated.value) void syncProcessingAlerts()
})
</script>

<template>
  <RouterView v-if="publicRoute" />

  <div v-else class="app-shell">
    <header
      class="app-header"
      :inert="modalActive"
      :aria-hidden="modalActive ? 'true' : undefined"
    >
      <div class="app-header__inner">
        <RouterLink class="app-header__brand" to="/" aria-label="Pewcorder library">
          <BrandMark compact />
        </RouterLink>
        <span class="app-header__status">{{ draftStatus }}</span>
        <button
          class="app-header__search"
          type="button"
          :aria-pressed="searchActive"
          aria-label="Search your library"
          @click="openSearch"
        >
          <Search :size="19" :stroke-width="1.7" aria-hidden="true" />
        </button>
        <RouterLink
          class="app-header__account"
          :class="{ 'app-header__account--connected': isAuthenticated }"
          to="/account"
          :aria-label="isAuthenticated ? 'Open connected account' : 'Sign in'"
        >
          <UserRound :size="20" :stroke-width="1.6" aria-hidden="true" />
        </RouterLink>
      </div>
    </header>

    <aside v-if="state === 'error'" class="recording-error" role="alert">
      <div>
        <strong>Recording needs attention</strong>
        <span>{{ errorMessage }}</span>
      </div>
      <button v-if="hasPendingRecording" type="button" @click="retrySave">Try saving again</button>
      <button v-else type="button" @click="clearError">Dismiss</button>
    </aside>

    <div
      class="app-content"
      :inert="modalActive"
      :aria-hidden="modalActive ? 'true' : undefined"
    >
      <RouterView />
    </div>
    <RecordSeal :state="state" :elapsed-seconds="elapsedSeconds" @toggle="toggle" />
    <DraftWizard
      v-if="wizardDraftId"
      :draft-id="wizardDraftId"
      @close="closeDraftWizard"
      @uploaded="onWizardUploaded"
    />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100svh;
  padding-top: var(--header-height);
}

.app-header {
  backdrop-filter: blur(14px);
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
  gap: 0.65rem;
  grid-template-columns: 1fr auto auto auto;
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
}

.app-header__search,
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
  text-decoration: none;
  width: 2.6rem;
}

.app-header__search[aria-pressed='true'],
.app-header__account--connected {
  background: var(--color-lapis);
  border-color: var(--color-lapis);
  color: var(--color-vellum-light);
}

.app-header__search:hover,
.app-header__search:focus-visible,
.app-header__account:hover,
.app-header__account:focus-visible {
  border-color: var(--color-lapis);
  color: var(--color-lapis);
}

.app-header__search[aria-pressed='true']:hover,
.app-header__search[aria-pressed='true']:focus-visible,
.app-header__account--connected:hover,
.app-header__account--connected:focus-visible {
  color: var(--color-vellum-light);
}

.app-header__search:focus-visible,
.app-header__account:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 3px;
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
  .app-shell {
    padding-bottom: calc(4.75rem + env(safe-area-inset-bottom));
  }

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
