<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Check,
  ChevronRight,
  LoaderCircle,
  MapPin,
  Mic,
  Trash2,
  Upload,
  X,
} from '@lucide/vue'
import { useAuth } from '../auth/useAuth'
import { useDraftRecorder } from '../recording/useDraftRecorder'
import type { DraftLocationStatus, LocalDraft } from '../recording/draftRepository'
import {
  createChurch,
  createPreacher,
  loadChurches,
  loadNearbyChurches,
  loadPreachers,
  updateSermonContext,
  type ChurchSuggestion,
  type OccasionKind,
  type ServerChurch,
  type ServerPreacher,
} from '../sermons/serverSermon'
import { uploadDraft } from '../upload/uploadDraft'

const props = defineProps<{
  draftId: string
}>()

const emit = defineEmits<{
  close: []
  uploaded: [sermonId: string]
}>()

const router = useRouter()
const { isAuthenticated } = useAuth()
const { drafts, removeDraft, refreshDrafts, closeDraftWizard, captureLocationForDraft } =
  useDraftRecorder()

type WizardStep = 'decide' | 'place' | 'details' | 'done'

const step = ref<WizardStep>('decide')
const modal = ref<HTMLElement>()
const sermonId = ref('')
const durationSeconds = ref(0)
const locationStatus = ref<DraftLocationStatus>('pending')
const latitude = ref<number>()
const longitude = ref<number>()
const churchName = ref('')
const churchAddress = ref('')
const selectedChurchId = ref('')
const churchLatitude = ref<number>()
const churchLongitude = ref<number>()
const preacherName = ref('')
const selectedPreacherId = ref('')
const occasionKind = ref<OccasionKind | ''>('')
const liturgicalDay = ref('')
const churches = ref<ServerChurch[]>([])
const preachers = ref<ServerPreacher[]>([])
const suggestions = ref<ChurchSuggestion[]>([])
const suggestionsBusy = ref(false)
const suggestionsMessage = ref('')
const selectedSuggestionId = ref('')
const processBusy = ref(false)
const processProgress = ref(0)
const discardBusy = ref(false)
const savingMeta = ref(false)
const actionError = ref('')
const confirmingDiscard = ref(false)

const occasionOptions: { value: OccasionKind; label: string }[] = [
  { value: 'sunday', label: 'Sunday' },
  { value: 'feast', label: 'Feast or holy day' },
  { value: 'wedding', label: 'Wedding' },
  { value: 'funeral', label: 'Funeral' },
  { value: 'midweek', label: 'Midweek service' },
  { value: 'other', label: 'Other occasion' },
]

const draft = computed(() => drafts.value.find((item) => item.id === props.draftId))

const durationLabel = computed(() => {
  const seconds = durationSeconds.value || draft.value?.durationSeconds || 0
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${minutes}:${String(remainder).padStart(2, '0')}`
})

const locationLabel = computed(() => {
  if (locationStatus.value === 'pending') return 'Finding where you were…'
  if (locationStatus.value === 'captured') return 'Place captured when you stopped recording'
  if (locationStatus.value === 'denied') return 'Location permission is off — choose a Church manually'
  return 'Location could not be read — choose a Church manually'
})

const stepIndex = computed(() => {
  if (step.value === 'decide') return 1
  if (step.value === 'place') return 2
  if (step.value === 'details') return 3
  return 4
})
const stepName = computed(() => {
  if (step.value === 'decide') return 'Process'
  if (step.value === 'place') return 'Place'
  if (step.value === 'details') return 'Details'
  return 'Done'
})

function syncLocationFromDraft(source: LocalDraft | undefined): void {
  if (!source) return
  durationSeconds.value = source.durationSeconds
  if (source.locationStatus) locationStatus.value = source.locationStatus
  if (source.latitude != null) latitude.value = source.latitude
  if (source.longitude != null) longitude.value = source.longitude
}

async function loadBooks(): Promise<void> {
  if (!isAuthenticated.value) {
    churches.value = []
    preachers.value = []
    return
  }
  try {
    const [loadedChurches, loadedPreachers] = await Promise.all([loadChurches(), loadPreachers()])
    churches.value = loadedChurches
    preachers.value = loadedPreachers
  } catch {
    churches.value = []
    preachers.value = []
  }
}

async function ensureCapturedPlace(): Promise<boolean> {
  if (locationStatus.value === 'captured' && latitude.value != null && longitude.value != null) {
    return true
  }
  if (locationStatus.value === 'denied') return false

  suggestionsBusy.value = true
  suggestionsMessage.value = 'Finding where you were…'
  try {
    if (draft.value) {
      const updated = await captureLocationForDraft(draft.value.id)
      syncLocationFromDraft(updated)
    }
    return locationStatus.value === 'captured' && latitude.value != null && longitude.value != null
  } finally {
    suggestionsBusy.value = false
  }
}

async function loadSuggestions(): Promise<void> {
  if (!isAuthenticated.value) {
    suggestionsMessage.value = 'Sign in to process before nearby Churches can be suggested.'
    return
  }

  const hasPlace = await ensureCapturedPlace()
  if (!hasPlace || latitude.value == null || longitude.value == null) {
    if (locationStatus.value === 'denied') {
      suggestionsMessage.value =
        'Location permission is off. Enable it in system settings, or enter a Church manually.'
    } else if (locationStatus.value === 'unavailable') {
      suggestionsMessage.value =
        'This device could not read a place fix. Enter a Church manually, or try again near a window.'
    } else {
      suggestionsMessage.value = 'Nearby suggestions need a captured place from this recording.'
    }
    return
  }

  suggestionsBusy.value = true
  suggestionsMessage.value = ''
  try {
    suggestions.value = await loadNearbyChurches(latitude.value, longitude.value)
    suggestionsMessage.value = suggestions.value.length
      ? `${suggestions.value.length} nearby ${suggestions.value.length === 1 ? 'Church' : 'Churches'}`
      : 'No nearby Churches found. Enter one manually.'
  } catch (error) {
    suggestions.value = []
    suggestionsMessage.value =
      error instanceof Error ? error.message : 'Nearby Churches could not be suggested.'
  } finally {
    suggestionsBusy.value = false
  }
}

function chooseSuggestion(suggestion: ChurchSuggestion): void {
  actionError.value = ''
  const existing = churches.value.find(
    (church) =>
      church.name.toLocaleLowerCase() === suggestion.name.toLocaleLowerCase() &&
      church.address.toLocaleLowerCase() === suggestion.address.toLocaleLowerCase(),
  )
  selectedChurchId.value = existing?.id ?? ''
  churchName.value = existing?.name ?? suggestion.name
  churchAddress.value = existing?.address ?? suggestion.address
  churchLatitude.value = suggestion.latitude
  churchLongitude.value = suggestion.longitude
  selectedSuggestionId.value = suggestion.provider_id
}

function clearChurchSelection(): void {
  selectedChurchId.value = ''
  selectedSuggestionId.value = ''
}

function chooseSavedChurch(id: string): void {
  selectedChurchId.value = id
  selectedSuggestionId.value = ''
  const church = churches.value.find((item) => item.id === id)
  if (!church) return
  churchName.value = church.name
  churchAddress.value = church.address
  churchLatitude.value = church.latitude != null ? Number(church.latitude) : undefined
  churchLongitude.value = church.longitude != null ? Number(church.longitude) : undefined
}

function chooseSavedPreacher(id: string): void {
  selectedPreacherId.value = id
  const preacher = preachers.value.find((item) => item.id === id)
  if (preacher) preacherName.value = preacher.name
}

async function processDraft(): Promise<void> {
  const current = draft.value
  if (!current || processBusy.value) return

  if (!isAuthenticated.value) {
    closeDraftWizard()
    await router.push({
      name: 'account',
      query: { redirect: `/?draft=${encodeURIComponent(props.draftId)}` },
    })
    return
  }

  processBusy.value = true
  processProgress.value = 0
  actionError.value = ''
  try {
    syncLocationFromDraft(current)
    const sermon = await uploadDraft(current, (progress) => {
      processProgress.value = progress
    })
    sermonId.value = sermon.id
    await removeDraft(props.draftId)
    await refreshDrafts()
    await loadBooks()
    step.value = 'place'
    void loadSuggestions()
  } catch (error) {
    actionError.value =
      error instanceof Error ? error.message : 'This Draft could not be sent for processing.'
  } finally {
    processBusy.value = false
  }
}

async function discardDraft(): Promise<void> {
  if (discardBusy.value) return
  discardBusy.value = true
  actionError.value = ''
  try {
    await removeDraft(props.draftId)
    await refreshDrafts()
    closeDraftWizard()
    emit('close')
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'This Draft could not be discarded.'
  } finally {
    discardBusy.value = false
    confirmingDiscard.value = false
  }
}

async function skipPlaceAndContinue(): Promise<void> {
  selectedChurchId.value = ''
  selectedSuggestionId.value = ''
  churchName.value = ''
  churchAddress.value = ''
  churchLatitude.value = undefined
  churchLongitude.value = undefined
  step.value = 'details'
}

async function savePlaceAndContinue(): Promise<void> {
  if (!sermonId.value) return
  savingMeta.value = true
  actionError.value = ''
  try {
    let churchId = selectedChurchId.value
    if (!churchId && churchName.value.trim()) {
      const church = await createChurch({
        name: churchName.value.trim(),
        address: churchAddress.value.trim(),
        ...(churchLatitude.value != null && churchLongitude.value != null
          ? {
              latitude: churchLatitude.value.toFixed(6),
              longitude: churchLongitude.value.toFixed(6),
            }
          : {}),
      })
      churchId = church.id
      selectedChurchId.value = church.id
      churches.value = [...churches.value, church].sort((left, right) =>
        left.name.localeCompare(right.name),
      )
    }
    if (churchId) {
      await updateSermonContext(sermonId.value, {
        church_id: churchId,
        preacher_id: null,
        occasion_kind: '',
        liturgical_day: '',
      })
    }
    step.value = 'details'
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Church details could not be saved.'
  } finally {
    savingMeta.value = false
  }
}

async function saveDetailsAndFinish(): Promise<void> {
  if (!sermonId.value) return
  savingMeta.value = true
  actionError.value = ''
  try {
    let preacherId = selectedPreacherId.value
    if (!preacherId && preacherName.value.trim()) {
      const preacher = await createPreacher(preacherName.value.trim())
      preacherId = preacher.id
      selectedPreacherId.value = preacher.id
      preachers.value = [...preachers.value, preacher].sort((left, right) =>
        left.name.localeCompare(right.name),
      )
    }

    await updateSermonContext(sermonId.value, {
      church_id: selectedChurchId.value || null,
      preacher_id: preacherId || null,
      occasion_kind: occasionKind.value,
      liturgical_day: liturgicalDay.value.trim(),
    })
    step.value = 'done'
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Details could not be saved.'
  } finally {
    savingMeta.value = false
  }
}

function finishToSermon(): void {
  const id = sermonId.value
  closeDraftWizard()
  if (id) emit('uploaded', id)
  else emit('close')
}

function dismiss(): void {
  if (sermonId.value) {
    finishToSermon()
    return
  }
  closeDraftWizard()
  emit('close')
}

watch(
  draft,
  (value) => {
    syncLocationFromDraft(value)
  },
  { immediate: true },
)

watch(locationStatus, (status, previous) => {
  if (step.value === 'place' && status === 'captured' && previous === 'pending') {
    void loadSuggestions()
  }
})

onMounted(async () => {
  document.body.classList.add('draft-wizard-lock')
  void loadBooks()
  await nextTick()
  modal.value?.focus()
})

onBeforeUnmount(() => {
  document.body.classList.remove('draft-wizard-lock')
})
</script>

<template>
  <div class="draft-wizard" role="presentation">
    <div class="draft-wizard__scrim" aria-hidden="true" @click="dismiss"></div>

    <div
      ref="modal"
      class="draft-wizard__modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="draft-wizard-title"
      tabindex="-1"
      @keydown.esc="dismiss"
    >
      <header class="draft-wizard__header">
        <div>
          <p class="rubric-label">Recording finished</p>
          <h1 id="draft-wizard-title">
            {{
              step === 'decide'
                ? 'Process this recording?'
                : step === 'place'
                  ? 'Where did you hear this?'
                  : step === 'details'
                    ? 'Add a few details'
                    : 'Processing has started'
            }}
          </h1>
        </div>
        <button class="draft-wizard__dismiss" type="button" aria-label="Close" @click="dismiss">
          <X :size="18" aria-hidden="true" />
        </button>
      </header>

      <div class="draft-wizard__progress" aria-hidden="true">
        <span :class="{ active: stepIndex >= 1 }"></span>
        <span :class="{ active: stepIndex >= 2 }"></span>
        <span :class="{ active: stepIndex >= 3 }"></span>
        <span :class="{ active: stepIndex >= 4 }"></span>
      </div>
      <p class="draft-wizard__step-status" aria-live="polite">
        Step {{ stepIndex }} of 4: {{ stepName }}
      </p>

      <section class="draft-wizard__summary">
        <span class="draft-wizard__seal" aria-hidden="true">
          <Mic :size="18" :stroke-width="1.7" />
        </span>
        <div>
          <strong>{{ durationLabel || 'Draft' }} captured</strong>
          <small>{{ locationLabel }}</small>
        </div>
      </section>

      <section v-if="step === 'decide'" class="draft-wizard__panel page-gather">
        <p class="rubric-label">Step 1 · Process</p>
        <p class="draft-wizard__lead">
          Your pew recording is safe on this device. Process it into your private library, or discard
          it now.
        </p>

        <p v-if="actionError" class="draft-wizard__error" role="alert">{{ actionError }}</p>

        <div v-if="!confirmingDiscard" class="draft-wizard__actions">
          <button
            type="button"
            class="draft-wizard__primary"
            :disabled="processBusy || !draft"
            @click="processDraft"
          >
            <LoaderCircle v-if="processBusy" class="spin" :size="18" aria-hidden="true" />
            <Upload v-else :size="18" aria-hidden="true" />
            {{
              processBusy
                ? `Processing ${Math.round(processProgress * 100)}%`
                : isAuthenticated
                  ? 'Process'
                  : 'Sign in to process'
            }}
          </button>
          <button
            type="button"
            class="draft-wizard__danger"
            :disabled="processBusy || discardBusy || !draft"
            @click="confirmingDiscard = true"
          >
            <Trash2 :size="16" aria-hidden="true" />
            Discard
          </button>
        </div>

        <div v-else class="draft-wizard__confirm">
          <p>Discard this recording from this device? This cannot be undone.</p>
          <button type="button" class="draft-wizard__ghost" @click="confirmingDiscard = false">
            Keep it
          </button>
          <button
            type="button"
            class="draft-wizard__danger"
            :disabled="discardBusy"
            @click="discardDraft"
          >
            {{ discardBusy ? 'Discarding…' : 'Discard recording' }}
          </button>
        </div>
      </section>

      <section v-else-if="step === 'place'" class="draft-wizard__panel page-gather">
        <p class="rubric-label">Step 2 · Place</p>
        <p class="draft-wizard__lead">
          Pewcorder captured your place when you stopped recording. Confirm a Church, or continue
          without one.
        </p>

        <label v-if="churches.length" class="draft-wizard__field">
          <span>Saved Churches</span>
          <select
            :value="selectedChurchId"
            @change="chooseSavedChurch(($event.target as HTMLSelectElement).value)"
          >
            <option value="">Choose from your place book</option>
            <option v-for="church in churches" :key="church.id" :value="church.id">
              {{ church.name }}
            </option>
          </select>
        </label>

        <div class="draft-wizard__nearby">
          <button
            type="button"
            :disabled="suggestionsBusy || locationStatus === 'pending'"
            @click="loadSuggestions"
          >
            <LoaderCircle v-if="suggestionsBusy" class="spin" :size="16" aria-hidden="true" />
            <MapPin v-else :size="16" aria-hidden="true" />
            {{ suggestionsBusy ? 'Looking nearby…' : 'Suggest nearby Churches' }}
          </button>
          <small v-if="suggestionsMessage">{{ suggestionsMessage }}</small>
        </div>

        <ul v-if="suggestions.length" class="draft-wizard__suggestions">
          <li v-for="suggestion in suggestions" :key="suggestion.provider_id">
            <button
              type="button"
              :class="{ 'is-selected': selectedSuggestionId === suggestion.provider_id }"
              :disabled="savingMeta"
              @click="chooseSuggestion(suggestion)"
            >
              <span>
                <strong>{{ suggestion.name }}</strong>
                <small>
                  {{ suggestion.address || 'Address not listed' }}
                  · {{ suggestion.distance_meters }}m
                </small>
              </span>
              <Check
                v-if="selectedSuggestionId === suggestion.provider_id"
                :size="18"
                aria-hidden="true"
              />
              <ChevronRight v-else :size="18" aria-hidden="true" />
            </button>
          </li>
        </ul>

        <label class="draft-wizard__field">
          <span>Church name</span>
          <input
            v-model="churchName"
            type="text"
            placeholder="Grace Parish"
            @input="clearChurchSelection"
          />
        </label>
        <label class="draft-wizard__field">
          <span>Address or note</span>
          <input
            v-model="churchAddress"
            type="text"
            placeholder="Optional"
            @input="clearChurchSelection"
          />
        </label>

        <p v-if="actionError" class="draft-wizard__error" role="alert">{{ actionError }}</p>

        <div class="draft-wizard__actions">
          <button
            type="button"
            class="draft-wizard__primary"
            :disabled="savingMeta"
            @click="savePlaceAndContinue"
          >
            Continue
          </button>
          <button
            type="button"
            class="draft-wizard__ghost"
            :disabled="savingMeta"
            @click="skipPlaceAndContinue"
          >
            Skip for now
          </button>
        </div>
      </section>

      <section v-else-if="step === 'details'" class="draft-wizard__panel page-gather">
        <p class="rubric-label">Step 3 · Details</p>
        <p class="draft-wizard__lead">Everything here is optional. You can refine it later.</p>

        <label v-if="preachers.length" class="draft-wizard__field">
          <span>Saved Preachers</span>
          <select
            :value="selectedPreacherId"
            @change="chooseSavedPreacher(($event.target as HTMLSelectElement).value)"
          >
            <option value="">Choose from your book</option>
            <option v-for="preacher in preachers" :key="preacher.id" :value="preacher.id">
              {{ preacher.name }}
            </option>
          </select>
        </label>

        <label class="draft-wizard__field">
          <span>Preacher</span>
          <input
            v-model="preacherName"
            type="text"
            placeholder="Rev. Miriam Cho"
            @input="selectedPreacherId = ''"
          />
        </label>

        <label class="draft-wizard__field">
          <span>Occasion</span>
          <select v-model="occasionKind">
            <option value="">Not specified</option>
            <option v-for="option in occasionOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="draft-wizard__field">
          <span>Liturgical day</span>
          <input v-model="liturgicalDay" type="text" placeholder="Third Sunday of Ordinary Time" />
        </label>

        <p v-if="actionError" class="draft-wizard__error" role="alert">{{ actionError }}</p>

        <div class="draft-wizard__actions">
          <button
            type="button"
            class="draft-wizard__primary"
            :disabled="savingMeta"
            @click="saveDetailsAndFinish"
          >
            {{ savingMeta ? 'Saving…' : 'Done' }}
          </button>
          <button type="button" class="draft-wizard__ghost" :disabled="savingMeta" @click="step = 'place'">
            Back
          </button>
        </div>
      </section>

      <section v-else class="draft-wizard__panel page-gather">
        <p class="rubric-label">Done</p>
        <p class="draft-wizard__lead">
          Your Sermon is in the library and processing has begun. Open it to follow along.
        </p>

        <ul class="draft-wizard__recap">
          <li>
            <Check :size="16" aria-hidden="true" />
            <span>Sent for private processing</span>
          </li>
          <li v-if="churchName.trim() || selectedChurchId">
            <Check :size="16" aria-hidden="true" />
            <span>{{ churchName.trim() || 'Church saved' }}</span>
          </li>
          <li v-if="preacherName.trim() || selectedPreacherId">
            <Check :size="16" aria-hidden="true" />
            <span>{{ preacherName.trim() || 'Preacher saved' }}</span>
          </li>
          <li v-if="locationStatus === 'captured'">
            <Check :size="16" aria-hidden="true" />
            <span>Place captured at stop</span>
          </li>
        </ul>

        <div class="draft-wizard__actions">
          <button type="button" class="draft-wizard__primary" @click="finishToSermon">
            Open Sermon
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.draft-wizard {
  align-items: center;
  bottom: 0;
  display: flex;
  justify-content: center;
  left: 0;
  padding: calc(var(--header-height) + 0.75rem) 0.85rem calc(1rem + env(safe-area-inset-bottom));
  position: fixed;
  right: 0;
  top: 0;
  z-index: 70;
}

.draft-wizard__scrim {
  backdrop-filter: blur(2px);
  background: color-mix(in srgb, var(--color-ink) 42%, transparent);
  border: 0;
  cursor: pointer;
  inset: 0;
  position: absolute;
}

.draft-wizard__modal {
  background:
    radial-gradient(ellipse at 50% 0%, rgba(184, 150, 62, 0.14), transparent 46%),
    var(--color-vellum);
  border: 1px solid var(--color-margin);
  box-shadow: 0 28px 70px rgba(28, 36, 48, 0.28);
  display: flex;
  flex-direction: column;
  max-height: min(42rem, calc(100svh - var(--header-height) - 2rem));
  max-width: 34rem;
  overflow: auto;
  padding: 1.35rem clamp(1rem, 3vw, 1.6rem) 1.6rem;
  position: relative;
  width: 100%;
  z-index: 1;
}

.draft-wizard__modal:focus {
  outline: 0;
}

.draft-wizard__header {
  align-items: start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.draft-wizard__header h1 {
  font-family: var(--font-display);
  font-size: clamp(1.7rem, 5vw, 2.45rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 42;
  font-weight: 500;
  letter-spacing: -0.04em;
  line-height: 0.98;
  margin: 0.35rem 0 0;
}

.draft-wizard__dismiss {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-margin);
  border-radius: 50%;
  color: var(--color-ink-muted);
  cursor: pointer;
  display: flex;
  height: 2.5rem;
  justify-content: center;
  width: 2.5rem;
}

.draft-wizard__progress {
  display: grid;
  gap: 0.4rem;
  grid-template-columns: repeat(4, 1fr);
  margin-top: 1.25rem;
}

.draft-wizard__progress span {
  background: var(--color-margin);
  display: block;
  height: 3px;
}

.draft-wizard__progress span.active {
  background: var(--color-rule-gold);
}

.draft-wizard__step-status {
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  height: 1px;
  overflow: hidden;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}

.draft-wizard__summary {
  align-items: center;
  border-bottom: 1px solid var(--color-rule-gold);
  display: flex;
  gap: 0.9rem;
  margin-top: 1.25rem;
  padding-bottom: 1.1rem;
}

.draft-wizard__seal {
  align-items: center;
  border: 1px solid var(--color-rule-gold);
  border-radius: 50%;
  color: var(--color-rubric);
  display: flex;
  height: 2.75rem;
  justify-content: center;
  width: 2.75rem;
}

.draft-wizard__summary strong,
.draft-wizard__summary small {
  display: block;
  font-family: var(--font-utility);
}

.draft-wizard__summary small {
  color: var(--color-ink-muted);
  font-size: 0.78rem;
  margin-top: 0.15rem;
}

.draft-wizard__panel {
  margin-top: 1.35rem;
}

.draft-wizard__lead {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.55;
  margin: 0.55rem 0 1.35rem;
}

.draft-wizard__field {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.draft-wizard__field > span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.draft-wizard__field input,
.draft-wizard__field select {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 1rem;
  min-height: 2.85rem;
  padding: 0.65rem 0.85rem;
}

.draft-wizard__nearby {
  margin-bottom: 1rem;
}

.draft-wizard__nearby button {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  gap: 0.45rem;
  min-height: 2.5rem;
  padding: 0.45rem 0.9rem;
}

.draft-wizard__nearby small {
  color: var(--color-ink-muted);
  display: block;
  font-family: var(--font-utility);
  font-size: 0.75rem;
  margin-top: 0.45rem;
}

.draft-wizard__suggestions {
  display: grid;
  gap: 0.55rem;
  list-style: none;
  margin: 0 0 1.25rem;
  padding: 0;
}

.draft-wizard__suggestions button {
  align-items: center;
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  cursor: pointer;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
  padding: 0.85rem 0.95rem;
  text-align: left;
  width: 100%;
}

.draft-wizard__suggestions button.is-selected {
  background: color-mix(in srgb, var(--color-lapis) 12%, var(--color-vellum-light));
  border-color: var(--color-lapis);
}

.draft-wizard__suggestions strong,
.draft-wizard__suggestions small {
  display: block;
  font-family: var(--font-utility);
}

.draft-wizard__suggestions small {
  color: var(--color-ink-muted);
  font-size: 0.78rem;
  margin-top: 0.2rem;
}

.draft-wizard__recap {
  display: grid;
  gap: 0.65rem;
  list-style: none;
  margin: 0 0 1.5rem;
  padding: 0;
}

.draft-wizard__recap li {
  align-items: center;
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.92rem;
  gap: 0.55rem;
}

.draft-wizard__recap svg {
  color: var(--color-lapis);
}

.draft-wizard__actions,
.draft-wizard__confirm {
  display: grid;
  gap: 0.65rem;
  margin-top: 1.5rem;
}

.draft-wizard__confirm p {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.9rem;
  margin: 0 0 0.35rem;
}

.draft-wizard__primary,
.draft-wizard__ghost,
.draft-wizard__danger {
  align-items: center;
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-weight: 650;
  gap: 0.5rem;
  justify-content: center;
  min-height: 3rem;
  padding: 0.7rem 1rem;
}

.draft-wizard__primary {
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
}

.draft-wizard__ghost {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  text-decoration: underline;
  text-underline-offset: 0.22rem;
}

.draft-wizard__danger {
  background: transparent;
  border: 1px solid var(--color-rubric);
  color: var(--color-rubric);
}

.draft-wizard__primary:disabled,
.draft-wizard__ghost:disabled,
.draft-wizard__danger:disabled {
  cursor: wait;
  opacity: 0.72;
}

.draft-wizard__error {
  color: var(--color-rubric);
  font-family: var(--font-utility);
  font-size: 0.8rem;
  margin: 0.5rem 0 0;
}

.spin {
  animation: wizard-spin 900ms linear infinite;
}

@keyframes wizard-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin {
    animation: none;
  }
}
</style>
