<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  BookOpenText,
  CalendarDays,
  Check,
  Clock3,
  Copy,
  LocateFixed,
  Mail,
  MapPin,
  PencilLine,
  Pause,
  Play,
  Share2,
  Trash2,
  UserRound,
  X,
} from '@lucide/vue'
import { useAuth } from '../auth/useAuth'
import { findNearbyChurches } from '../location/findNearbyChurches'
import {
  createChurch,
  createPreacher,
  createShareLink,
  loadChurches,
  loadPreachers,
  loadShareLink,
  loadServerSermon,
  revokeShareLink,
  saveReflection,
  serverSermonDuration,
  serverSermonTitle,
  updateStudyArtifact,
  updateSermonContext,
  updateTranscript,
  type OccasionKind,
  type ChurchSuggestion,
  type ServerChurch,
  type ServerPreacher,
  type ServerShareLink,
  type ServerSermonDetail,
  type ServerTranscriptSegment,
  type StudyArtifactKind,
} from '../sermons/serverSermon'

type Section = 'study' | 'transcript' | 'discuss' | 'reflection'

const route = useRoute()
const router = useRouter()
const { isAuthenticated } = useAuth()
const sermon = ref<ServerSermonDetail>()
const loading = ref(true)
const errorMessage = ref('')
const activeSection = ref<Section>('study')
const audio = ref<HTMLAudioElement>()
const playing = ref(false)
const currentSeconds = ref(0)
const playbackError = ref(false)
const editingKind = ref<StudyArtifactKind>()
const editContent = ref('')
const savingEdit = ref(false)
const editMessage = ref('')
const editingTranscript = ref(false)
const transcriptEdits = ref<Pick<ServerTranscriptSegment, 'start_seconds' | 'text'>[]>([])
const savingTranscript = ref(false)
const transcriptMessage = ref('')
const reflectionPrompt = 'Where is this sermon asking for one faithful action?'
const reflectionContent = ref('')
const savingReflection = ref(false)
const reflectionMessage = ref('')
const sharePanelOpen = ref(false)
const shareLink = ref<ServerShareLink | null>(null)
const shareLoading = ref(false)
const shareBusy = ref(false)
const shareMessage = ref('')
const contextPanelOpen = ref(false)
const contextLoading = ref(false)
const contextSaving = ref(false)
const contextMessage = ref('')
const churches = ref<ServerChurch[]>([])
const preachers = ref<ServerPreacher[]>([])
const selectedChurchId = ref('')
const selectedPreacherId = ref('')
const selectedOccasionKind = ref<OccasionKind | ''>('')
const liturgicalDay = ref('')
const addingChurch = ref(false)
const newChurchName = ref('')
const newChurchAddress = ref('')
const churchSuggestions = ref<ChurchSuggestion[]>([])
const findingChurches = ref(false)
const addingPreacher = ref(false)
const newPreacherName = ref('')

const progress = computed(() =>
  sermon.value ? Math.min(currentSeconds.value / sermon.value.duration_seconds, 1) : 0,
)
const progressLabel = computed(() => `${Math.round(progress.value * 100)}%`)
const capturedDate = computed(() =>
  sermon.value
    ? new Intl.DateTimeFormat(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      }).format(new Date(sermon.value.captured_at))
    : '',
)
const occasionOptions: [OccasionKind, string][] = [
  ['sunday', 'Sunday'],
  ['feast', 'Feast'],
  ['wedding', 'Wedding'],
  ['funeral', 'Funeral'],
  ['midweek', 'Midweek'],
  ['other', 'Other'],
]

function occasionLabel(kind: OccasionKind | ''): string {
  return occasionOptions.find(([value]) => value === kind)?.[1] ?? ''
}

function artifact(kind: StudyArtifactKind): string {
  return sermon.value?.study_artifacts.find((candidate) => candidate.kind === kind)?.content ?? ''
}

function numberedItems(content: string): string[] {
  return content
    .split(/\n+/)
    .map((item) => item.replace(/^\s*\d+\.\s*/, '').trim())
    .filter(Boolean)
}

function paragraphs(content: string): string[] {
  return content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
}

function timestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}

function scriptureUrl(display: string): string {
  return `https://www.biblegateway.com/passage/?search=${encodeURIComponent(display)}`
}

function beginArtifactEdit(kind: StudyArtifactKind): void {
  editingKind.value = kind
  editContent.value = artifact(kind)
  editMessage.value = ''
}

function cancelArtifactEdit(): void {
  editingKind.value = undefined
  editContent.value = ''
  editMessage.value = ''
}

async function saveArtifactEdit(): Promise<void> {
  if (!sermon.value || !editingKind.value || savingEdit.value) return
  savingEdit.value = true
  editMessage.value = ''
  try {
    const saved = await updateStudyArtifact(
      sermon.value.id,
      editingKind.value,
      editContent.value,
    )
    const index = sermon.value.study_artifacts.findIndex(
      (candidate) => candidate.kind === saved.kind,
    )
    if (index >= 0) sermon.value.study_artifacts[index] = saved
    editingKind.value = undefined
    editMessage.value = 'Your edit was saved.'
  } catch (error) {
    editMessage.value = error instanceof Error ? error.message : 'This edit could not be saved.'
  } finally {
    savingEdit.value = false
  }
}

function beginTranscriptEdit(): void {
  transcriptEdits.value = (sermon.value?.transcript?.segments ?? []).map((segment) => ({
    start_seconds: segment.start_seconds,
    text: segment.text,
  }))
  transcriptMessage.value = ''
  editingTranscript.value = true
}

function cancelTranscriptEdit(): void {
  transcriptEdits.value = []
  transcriptMessage.value = ''
  editingTranscript.value = false
}

async function saveTranscriptEdit(): Promise<void> {
  if (!sermon.value || savingTranscript.value) return
  savingTranscript.value = true
  transcriptMessage.value = ''
  try {
    sermon.value.transcript = await updateTranscript(sermon.value.id, transcriptEdits.value)
    editingTranscript.value = false
    transcriptMessage.value = 'Transcript corrections saved.'
  } catch (error) {
    transcriptMessage.value =
      error instanceof Error ? error.message : 'Transcript corrections could not be saved.'
  } finally {
    savingTranscript.value = false
  }
}

async function persistReflection(): Promise<void> {
  if (!sermon.value || savingReflection.value) return
  savingReflection.value = true
  reflectionMessage.value = ''
  try {
    const existing = sermon.value.reflections[0]
    const saved = await saveReflection(sermon.value.id, {
      id: existing?.id,
      prompt: reflectionPrompt,
      content: reflectionContent.value,
    })
    if (existing) sermon.value.reflections[0] = saved
    else sermon.value.reflections.push(saved)
    reflectionContent.value = saved.content
    reflectionMessage.value = 'Reflection saved privately.'
  } catch (error) {
    reflectionMessage.value =
      error instanceof Error ? error.message : 'Your Reflection could not be saved.'
  } finally {
    savingReflection.value = false
  }
}

function selectSection(section: Section) {
  activeSection.value = section
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function togglePlayback(): Promise<void> {
  if (!audio.value) return
  playbackError.value = false
  if (playing.value) {
    audio.value.pause()
    return
  }
  try {
    await audio.value.play()
  } catch {
    playbackError.value = true
  }
}

async function seekTo(seconds: number): Promise<void> {
  if (!audio.value) return
  audio.value.currentTime = seconds
  currentSeconds.value = seconds
  playbackError.value = false
  try {
    await audio.value.play()
  } catch {
    playbackError.value = true
  }
}

async function toggleSharePanel(): Promise<void> {
  sharePanelOpen.value = !sharePanelOpen.value
  shareMessage.value = ''
  if (!sharePanelOpen.value || !sermon.value) return
  shareLoading.value = true
  try {
    shareLink.value = await loadShareLink(sermon.value.id)
  } catch (error) {
    shareMessage.value =
      error instanceof Error ? error.message : 'Sharing details could not be loaded.'
  } finally {
    shareLoading.value = false
  }
}

async function publishShareLink(): Promise<void> {
  if (!sermon.value || shareBusy.value) return
  shareBusy.value = true
  shareMessage.value = ''
  try {
    shareLink.value = await createShareLink(sermon.value.id)
    shareMessage.value = 'Your unlisted link is ready.'
  } catch (error) {
    shareMessage.value =
      error instanceof Error ? error.message : 'An unlisted link could not be created.'
  } finally {
    shareBusy.value = false
  }
}

async function copyShareLink(): Promise<void> {
  if (!shareLink.value) return
  try {
    await navigator.clipboard.writeText(shareLink.value.url)
    shareMessage.value = 'Link copied.'
  } catch {
    shareMessage.value = 'Select the link above to copy it.'
  }
}

function selectShareLink(event: FocusEvent): void {
  if (event.target instanceof HTMLInputElement) event.target.select()
}

async function shareNative(): Promise<void> {
  if (!shareLink.value || !sermon.value) return
  if (!navigator.share) {
    await copyShareLink()
    return
  }
  try {
    await navigator.share({
      title: serverSermonTitle(sermon.value),
      text: 'Listen and read this Sermon in Pewcorder.',
      url: shareLink.value.url,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    shareMessage.value = 'This link could not be shared from the device.'
  }
}

async function unpublishShareLink(): Promise<void> {
  if (!sermon.value || !shareLink.value || shareBusy.value) return
  shareBusy.value = true
  shareMessage.value = ''
  try {
    await revokeShareLink(sermon.value.id)
    shareLink.value = null
    shareMessage.value = 'The old link no longer opens this Sermon.'
  } catch (error) {
    shareMessage.value =
      error instanceof Error ? error.message : 'The unlisted link could not be revoked.'
  } finally {
    shareBusy.value = false
  }
}

async function toggleContextPanel(): Promise<void> {
  contextPanelOpen.value = !contextPanelOpen.value
  contextMessage.value = ''
  churchSuggestions.value = []
  if (!contextPanelOpen.value || !sermon.value) return
  selectedChurchId.value = sermon.value.church?.id ?? ''
  selectedPreacherId.value = sermon.value.preacher?.id ?? ''
  selectedOccasionKind.value = sermon.value.occasion_kind
  liturgicalDay.value = sermon.value.liturgical_day
  contextLoading.value = true
  try {
    const [savedChurches, savedPreachers] = await Promise.all([
      loadChurches(),
      loadPreachers(),
    ])
    churches.value = savedChurches
    preachers.value = savedPreachers
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'Sermon details could not be loaded.'
  } finally {
    contextLoading.value = false
  }
}

async function saveNewChurch(): Promise<void> {
  if (!newChurchName.value.trim() || contextSaving.value) return
  contextSaving.value = true
  contextMessage.value = ''
  try {
    const saved = await createChurch({
      name: newChurchName.value,
      address: newChurchAddress.value,
    })
    churches.value.push(saved)
    churches.value.sort((left, right) => left.name.localeCompare(right.name))
    selectedChurchId.value = saved.id
    newChurchName.value = ''
    newChurchAddress.value = ''
    addingChurch.value = false
    contextMessage.value = 'Church saved to your personal place book.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'This Church could not be saved.'
  } finally {
    contextSaving.value = false
  }
}

async function suggestNearbyChurches(): Promise<void> {
  if (findingChurches.value) return
  findingChurches.value = true
  churchSuggestions.value = []
  contextMessage.value = ''
  try {
    churchSuggestions.value = await findNearbyChurches()
    contextMessage.value = churchSuggestions.value.length
      ? 'Choose a nearby Church to add it to your private place book.'
      : 'No nearby Churches were found. You can still add one manually.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'Nearby Churches could not be suggested.'
  } finally {
    findingChurches.value = false
  }
}

async function chooseChurchSuggestion(suggestion: ChurchSuggestion): Promise<void> {
  const normalized = (value: string) => value.trim().toLocaleLowerCase()
  const existing = churches.value.find(
    (church) =>
      normalized(church.name) === normalized(suggestion.name) &&
      normalized(church.address) === normalized(suggestion.address),
  )
  if (existing) {
    selectedChurchId.value = existing.id
    churchSuggestions.value = []
    contextMessage.value = 'This Church is already in your private place book.'
    return
  }

  contextSaving.value = true
  try {
    const saved = await createChurch({
      name: suggestion.name,
      address: suggestion.address,
      latitude: suggestion.latitude.toFixed(7),
      longitude: suggestion.longitude.toFixed(7),
    })
    churches.value.push(saved)
    churches.value.sort((left, right) => left.name.localeCompare(right.name))
    selectedChurchId.value = saved.id
    churchSuggestions.value = []
    contextMessage.value = 'Church saved. Save details to assign it to this Sermon.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'This Church could not be saved.'
  } finally {
    contextSaving.value = false
  }
}

async function saveNewPreacher(): Promise<void> {
  if (!newPreacherName.value.trim() || contextSaving.value) return
  contextSaving.value = true
  contextMessage.value = ''
  try {
    const saved = await createPreacher(newPreacherName.value)
    preachers.value.push(saved)
    preachers.value.sort((left, right) => left.name.localeCompare(right.name))
    selectedPreacherId.value = saved.id
    newPreacherName.value = ''
    addingPreacher.value = false
    contextMessage.value = 'Preacher saved to your personal preacher book.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'This Preacher could not be saved.'
  } finally {
    contextSaving.value = false
  }
}

async function saveContext(): Promise<void> {
  if (!sermon.value || contextSaving.value) return
  contextSaving.value = true
  contextMessage.value = ''
  try {
    const saved = await updateSermonContext(sermon.value.id, {
      church_id: selectedChurchId.value || null,
      preacher_id: selectedPreacherId.value || null,
      occasion_kind: selectedOccasionKind.value,
      liturgical_day: liturgicalDay.value,
    })
    sermon.value.church = saved.church
    sermon.value.preacher = saved.preacher
    sermon.value.occasion_kind = saved.occasion_kind
    sermon.value.liturgical_day = saved.liturgical_day
    contextPanelOpen.value = false
  } catch (error) {
    contextMessage.value =
      error instanceof Error ? error.message : 'These Sermon details could not be saved.'
  } finally {
    contextSaving.value = false
  }
}

async function load(id: string): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  sermon.value = undefined
  editingKind.value = undefined
  editMessage.value = ''
  reflectionMessage.value = ''
  sharePanelOpen.value = false
  shareLink.value = null
  shareMessage.value = ''
  contextPanelOpen.value = false
  contextMessage.value = ''
  try {
    const loadedSermon = await loadServerSermon(id)
    if (loadedSermon.processing_status !== 'ready') {
      errorMessage.value = loadedSermon.processing_message
      return
    }
    sermon.value = loadedSermon
    reflectionContent.value = loadedSermon.reflections[0]?.content ?? ''
  } catch (error) {
    if (!isAuthenticated.value) {
      await router.replace({
        name: 'account',
        query: { redirect: `/sermons/${encodeURIComponent(id)}` },
      })
      return
    }
    errorMessage.value = error instanceof Error ? error.message : 'This Sermon could not be opened.'
  } finally {
    loading.value = false
  }
}

watch(
  () => String(route.params.id),
  (id) => void load(id),
  { immediate: true },
)

watch(
  () => route.hash,
  (hash) => {
    if (hash === '#reflection') activeSection.value = 'reflection'
  },
  { immediate: true },
)
</script>

<template>
  <main class="sermon-detail page-gather">
    <button class="back-link" type="button" @click="router.push('/')">
      <ArrowLeft :size="17" :stroke-width="1.7" aria-hidden="true" />
      Library
    </button>

    <p v-if="loading" class="detail-state" role="status">Opening your Sermon…</p>
    <section v-else-if="errorMessage" class="detail-state detail-state--error" role="alert">
      <p class="rubric-label">Unable to open</p>
      <h1>{{ errorMessage }}</h1>
    </section>

    <article v-else-if="sermon">
      <header class="sermon-header">
        <div class="sermon-header__rubric">
          <span>{{ sermon.liturgical_day || 'Pew recording' }}</span>
          <span v-if="sermon.occasion_kind">{{ occasionLabel(sermon.occasion_kind) }}</span>
          <span>Ready</span>
        </div>
        <h1>{{ serverSermonTitle(sermon) }}</h1>
        <div class="sermon-header__meta">
          <span v-if="sermon.preacher">
            <UserRound :size="15" aria-hidden="true" />{{ sermon.preacher.name }}
          </span>
          <span v-if="sermon.church">
            <MapPin :size="15" aria-hidden="true" />{{ sermon.church.name }}
          </span>
          <span><CalendarDays :size="15" aria-hidden="true" />{{ capturedDate }}</span>
          <span>
            <Clock3 :size="15" aria-hidden="true" />{{
              serverSermonDuration(sermon.duration_seconds)
            }}
          </span>
        </div>
        <div class="sermon-header__actions">
          <button type="button" @click="toggleContextPanel">
            <PencilLine :size="16" aria-hidden="true" />
            {{ contextPanelOpen ? 'Close details' : 'Edit details' }}
          </button>
          <button type="button" @click="toggleSharePanel">
            <Share2 :size="16" aria-hidden="true" />
            {{ sharePanelOpen ? 'Close sharing' : 'Share sermon' }}
          </button>
          <button type="button" @click="router.push(`/sermons/${sermon.id}/email`)">
            <Mail :size="16" aria-hidden="true" />
            Email handout
          </button>
        </div>
      </header>

      <section v-if="contextPanelOpen" class="context-panel" aria-label="Sermon details">
        <div class="context-panel__heading">
          <p class="rubric-label">Personal context</p>
          <h2>Where and when you heard it</h2>
          <p>Reuse Churches and Preachers from your private books. None of these details block recording.</p>
        </div>
        <p v-if="contextLoading" class="context-panel__status" role="status">
          Opening your saved details…
        </p>
        <div v-else class="context-fields">
          <div class="context-field">
            <label for="sermon-church">Church</label>
            <select id="sermon-church" v-model="selectedChurchId">
              <option value="">Unassigned</option>
              <option v-for="church in churches" :key="church.id" :value="church.id">
                {{ church.name }}{{ church.address ? ` · ${church.address}` : '' }}
              </option>
            </select>
            <button
              class="context-field__locate"
              type="button"
              :disabled="findingChurches || contextSaving"
              @click="suggestNearbyChurches"
            >
              <LocateFixed :size="15" aria-hidden="true" />
              {{ findingChurches ? 'Finding nearby…' : 'Find nearby Churches' }}
            </button>
            <div v-if="churchSuggestions.length" class="church-suggestions">
              <button
                v-for="suggestion in churchSuggestions"
                :key="suggestion.provider_id"
                type="button"
                @click="chooseChurchSuggestion(suggestion)"
              >
                <span>
                  <strong>{{ suggestion.name }}</strong>
                  <small v-if="suggestion.address">{{ suggestion.address }}</small>
                </span>
                <small>{{ suggestion.distance_meters }} m</small>
              </button>
            </div>
            <button type="button" @click="addingChurch = !addingChurch">
              {{ addingChurch ? 'Cancel new Church' : 'Add a Church' }}
            </button>
            <div v-if="addingChurch" class="context-new">
              <input
                v-model="newChurchName"
                type="text"
                placeholder="Church name"
                aria-label="New Church name"
              />
              <input
                v-model="newChurchAddress"
                type="text"
                placeholder="Address (optional)"
                aria-label="New Church address"
              />
              <button
                type="button"
                :disabled="contextSaving || !newChurchName.trim()"
                @click="saveNewChurch"
              >
                Save Church
              </button>
            </div>
          </div>

          <div class="context-field">
            <label for="sermon-preacher">Preacher</label>
            <select id="sermon-preacher" v-model="selectedPreacherId">
              <option value="">Unassigned</option>
              <option v-for="preacher in preachers" :key="preacher.id" :value="preacher.id">
                {{ preacher.name }}
              </option>
            </select>
            <button type="button" @click="addingPreacher = !addingPreacher">
              {{ addingPreacher ? 'Cancel new Preacher' : 'Add a Preacher' }}
            </button>
            <div v-if="addingPreacher" class="context-new">
              <input
                v-model="newPreacherName"
                type="text"
                placeholder="Preacher name"
                aria-label="New Preacher name"
              />
              <button
                type="button"
                :disabled="contextSaving || !newPreacherName.trim()"
                @click="saveNewPreacher"
              >
                Save Preacher
              </button>
            </div>
          </div>

          <div class="context-field">
            <label for="sermon-occasion">Occasion kind</label>
            <select id="sermon-occasion" v-model="selectedOccasionKind">
              <option value="">Unassigned</option>
              <option v-for="[value, label] in occasionOptions" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </div>

          <div class="context-field">
            <label for="sermon-liturgical-day">Liturgical day</label>
            <input
              id="sermon-liturgical-day"
              v-model="liturgicalDay"
              type="text"
              placeholder="e.g. Third Sunday of Ordinary Time"
            />
          </div>
        </div>
        <div class="context-panel__footer">
          <span role="status">{{ contextMessage }}</span>
          <button type="button" :disabled="contextSaving || contextLoading" @click="saveContext">
            {{ contextSaving ? 'Saving…' : 'Save details' }}
          </button>
        </div>
      </section>

      <section v-if="sharePanelOpen" class="share-panel" aria-label="Share this Sermon">
        <div>
          <p class="rubric-label">Unlisted page</p>
          <h2>Share the sermon, never your Reflection</h2>
          <p>
            Anyone with the link can read the Study artifacts and Transcript and listen to the
            recording. Your private Reflection is always excluded.
          </p>
        </div>
        <p v-if="shareLoading" class="share-panel__status" role="status">
          Checking for an existing link…
        </p>
        <template v-else-if="shareLink">
          <input
            :value="shareLink.url"
            aria-label="Unlisted Sermon link"
            readonly
            @focus="selectShareLink"
          />
          <div class="share-panel__actions">
            <button type="button" :disabled="shareBusy" @click="shareNative">
              <Share2 :size="16" aria-hidden="true" /> Share link
            </button>
            <button type="button" :disabled="shareBusy" @click="copyShareLink">
              <Copy :size="16" aria-hidden="true" /> Copy
            </button>
            <button type="button" :disabled="shareBusy" @click="unpublishShareLink">
              <Trash2 :size="16" aria-hidden="true" /> Revoke
            </button>
          </div>
        </template>
        <button
          v-else
          class="share-panel__publish"
          type="button"
          :disabled="shareBusy"
          @click="publishShareLink"
        >
          <Share2 :size="16" aria-hidden="true" />
          {{ shareBusy ? 'Creating…' : 'Create unlisted link' }}
        </button>
        <p v-if="shareMessage" class="share-panel__status" role="status">{{ shareMessage }}</p>
      </section>

      <section class="audio-player" aria-label="Sermon audio player">
        <audio
          ref="audio"
          :src="sermon.audio_url"
          preload="metadata"
          @play="playing = true"
          @pause="playing = false"
          @ended="playing = false"
          @timeupdate="currentSeconds = audio?.currentTime ?? 0"
          @error="playbackError = true"
        ></audio>
        <button
          class="audio-player__play"
          type="button"
          :aria-label="playing ? 'Pause sermon' : 'Play sermon'"
          @click="togglePlayback"
        >
          <Pause v-if="playing" :size="21" fill="currentColor" aria-hidden="true" />
          <Play v-else :size="21" fill="currentColor" aria-hidden="true" />
        </button>
        <div class="audio-player__body">
          <div class="audio-player__labels">
            <span>{{ playing ? 'Playing sermon' : 'Sermon audio' }}</span>
            <span>{{ progressLabel }} · {{ serverSermonDuration(sermon.duration_seconds) }}</span>
          </div>
          <div class="audio-player__track" aria-hidden="true">
            <span :style="{ width: progressLabel }"></span>
          </div>
          <small v-if="playbackError" class="audio-player__error">
            Audio could not be played. Reopen this Sermon to refresh its private link.
          </small>
        </div>
      </section>

      <nav class="section-tabs" aria-label="Sermon sections">
        <button
          v-for="section in ([
            ['study', 'Study'],
            ['transcript', 'Transcript'],
            ['discuss', 'Discuss'],
            ['reflection', 'Reflect'],
          ] as [Section, string][])"
          :key="section[0]"
          type="button"
          :class="{ active: activeSection === section[0] }"
          @click="selectSection(section[0])"
        >
          {{ section[1] }}
        </button>
      </nav>

      <p v-if="editMessage" class="edit-message" role="status">{{ editMessage }}</p>

      <div class="sermon-content">
        <template v-if="activeSection === 'study'">
          <section class="artifact artifact--lead">
            <div class="artifact__heading">
              <p class="rubric-label">In brief</p>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit short summary"
                @click="beginArtifactEdit('short_summary')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'short_summary'" class="artifact-editor">
              <textarea v-model="editContent" rows="6" aria-label="Short summary"></textarea>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <p v-else class="artifact__summary">{{ artifact('short_summary') }}</p>
          </section>

          <section v-if="sermon.scripture_references.length" class="artifact">
            <div class="artifact__heading">
              <h2>Scripture</h2>
            </div>
            <div class="scripture-links">
              <a
                v-for="reference in sermon.scripture_references"
                :key="reference.display"
                :href="scriptureUrl(reference.display)"
                target="_blank"
                rel="noreferrer"
              >
                <BookOpenText :size="17" :stroke-width="1.6" aria-hidden="true" />
                {{ reference.display }}
              </a>
            </div>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Long summary</h2>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit long summary"
                @click="beginArtifactEdit('long_summary')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'long_summary'" class="artifact-editor">
              <textarea v-model="editContent" rows="12" aria-label="Long summary"></textarea>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <div v-else class="artifact__prose">
              <p v-for="paragraph in paragraphs(artifact('long_summary'))" :key="paragraph">
                {{ paragraph }}
              </p>
            </div>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Outline</h2>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit outline"
                @click="beginArtifactEdit('outline')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'outline'" class="artifact-editor">
              <textarea v-model="editContent" rows="9" aria-label="Outline"></textarea>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <ol v-else class="outline">
              <li v-for="item in numberedItems(artifact('outline'))" :key="item">
                <span>{{ item }}</span>
              </li>
            </ol>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Tags</h2>
            </div>
            <div class="tag-list">
              <span v-for="tag in sermon.tag_suggestions" :key="tag">{{ tag }}</span>
            </div>
          </section>

          <section v-if="sermon.related_sermons.length" class="artifact">
            <div class="artifact__heading">
              <h2>Related Sermons</h2>
            </div>
            <div class="related-sermons">
              <RouterLink
                v-for="related in sermon.related_sermons"
                :key="related.id"
                :to="`/sermons/${related.id}`"
              >
                <strong>{{ serverSermonTitle(related) }}</strong>
                <span>{{ related.reason }}</span>
              </RouterLink>
            </div>
          </section>
        </template>

        <template v-else-if="activeSection === 'transcript'">
          <section class="artifact transcript">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Cleaned transcript</p>
                <h2>Follow the sermon</h2>
              </div>
              <button
                v-if="sermon.transcript?.segments.length"
                class="artifact__edit"
                type="button"
                aria-label="Edit Transcript"
                @click="beginTranscriptEdit"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <p class="transcript__note">Side conversations have been removed. Tap a timestamp to listen from that moment.</p>
            <div v-if="editingTranscript" class="transcript-editor">
              <label
                v-for="(segment, index) in transcriptEdits"
                :key="segment.start_seconds"
              >
                <span>{{ timestamp(segment.start_seconds) }}</span>
                <textarea
                  v-model="transcriptEdits[index]!.text"
                  rows="3"
                  :aria-label="`Transcript at ${timestamp(segment.start_seconds)}`"
                ></textarea>
              </label>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelTranscriptEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingTranscript" @click="saveTranscriptEdit">
                  <Check :size="15" />{{ savingTranscript ? 'Saving…' : 'Save corrections' }}
                </button>
              </div>
            </div>
            <div v-else class="transcript__segments">
              <div
                v-for="segment in sermon.transcript?.segments ?? []"
                :key="`${segment.start_seconds}-${segment.text}`"
                class="transcript__segment"
              >
                <button type="button" @click="seekTo(segment.start_seconds)">
                  {{ timestamp(segment.start_seconds) }}
                </button>
                <p>{{ segment.text }}</p>
              </div>
            </div>
            <p v-if="transcriptMessage" class="artifact__message" role="status">
              {{ transcriptMessage }}
            </p>
          </section>
        </template>

        <template v-else-if="activeSection === 'discuss'">
          <section class="artifact question-set">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Around the table</p>
                <h2>Discussion questions</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit adult discussion questions"
                @click="beginArtifactEdit('adult_discussion_questions')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'adult_discussion_questions'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="9"
                aria-label="Adult discussion questions"
              ></textarea>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <ol v-else>
              <li
                v-for="question in numberedItems(artifact('adult_discussion_questions'))"
                :key="question"
              >
                {{ question }}
              </li>
            </ol>
          </section>
          <section class="artifact question-set question-set--kids">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">With children</p>
                <h2>Questions for younger listeners</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit kids discussion questions"
                @click="beginArtifactEdit('kids_discussion_questions')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'kids_discussion_questions'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="9"
                aria-label="Kids discussion questions"
              ></textarea>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <ol v-else>
              <li
                v-for="question in numberedItems(artifact('kids_discussion_questions'))"
                :key="question"
              >
                {{ question }}
              </li>
            </ol>
          </section>
        </template>

        <template v-else>
          <section id="reflection" class="artifact reflection">
            <p class="rubric-label">Private to you</p>
            <h2>Reflection</h2>
            <p class="reflection__prompt">{{ reflectionPrompt }}</p>
            <textarea
              v-model="reflectionContent"
              rows="8"
              aria-label="Your private reflection"
              placeholder="Begin writing…"
            ></textarea>
            <div class="reflection__footer">
              <span>{{ reflectionMessage || 'Only you can see this Reflection.' }}</span>
              <button
                type="button"
                :disabled="savingReflection || !reflectionContent.trim()"
                @click="persistReflection"
              >
                {{ savingReflection ? 'Saving…' : 'Save reflection' }}
              </button>
            </div>
          </section>
        </template>
      </div>
    </article>
  </main>
</template>

<style scoped>
.sermon-detail {
  margin: 0 auto;
  max-width: 58rem;
  padding: 2rem clamp(1.25rem, 5vw, 3.5rem) 10rem;
}

.back-link {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  gap: 0.4rem;
  margin-bottom: 2.5rem;
  padding: 0.5rem 0;
}

.detail-state {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  padding: 4rem 0;
}

.detail-state--error h1 {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 7vw, 4.5rem);
  font-weight: 520;
  letter-spacing: -0.05em;
  line-height: 0.98;
  max-width: 13ch;
}

.sermon-header {
  border-bottom: 1px solid var(--color-rule-gold);
  padding-bottom: 2.25rem;
}

.sermon-header__rubric {
  color: var(--color-rubric);
  display: flex;
  flex-wrap: wrap;
  font-family: var(--font-utility);
  font-size: 0.7rem;
  font-weight: 700;
  gap: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.sermon-header__rubric span + span::before {
  color: var(--color-rule-gold);
  content: '·';
  margin-right: 0.75rem;
}

.sermon-header h1 {
  font-family: var(--font-display);
  font-size: clamp(2.8rem, 8vw, 5.7rem);
  font-variation-settings: 'opsz' 90, 'SOFT' 44;
  font-weight: 500;
  letter-spacing: -0.06em;
  line-height: 0.92;
  margin: 0.8rem 0 1.25rem;
  max-width: 11ch;
}

.sermon-header__preacher {
  font-family: var(--font-reading);
  font-size: 1.1rem;
  font-style: italic;
}

.sermon-header__meta {
  color: var(--color-ink-muted);
  display: flex;
  flex-wrap: wrap;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  gap: 0.55rem 1.15rem;
  margin-top: 1rem;
}

.sermon-header__meta span {
  align-items: center;
  display: inline-flex;
  gap: 0.3rem;
}

.sermon-header__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.sermon-header__actions button {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  gap: 0.5rem;
  min-height: 2.75rem;
  padding: 0.6rem 0.9rem;
}

.context-panel {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  margin: 1.5rem 0;
  padding: clamp(1.25rem, 4vw, 2rem);
}

.context-panel__heading h2 {
  font-family: var(--font-display);
  font-size: clamp(1.65rem, 4vw, 2.25rem);
  font-variation-settings: 'opsz' 38, 'SOFT' 48;
  font-weight: 540;
  letter-spacing: -0.035em;
  margin: 0.35rem 0 0;
}

.context-panel__heading > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.6;
  margin: 0.8rem 0 1.25rem;
  max-width: 44rem;
}

.context-fields {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.context-field > label {
  color: var(--color-rubric);
  display: block;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  margin-bottom: 0.45rem;
  text-transform: uppercase;
}

.context-field > input,
.context-field > select,
.context-new input {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 0.9rem;
  min-height: 2.75rem;
  padding: 0.6rem 0.75rem;
  width: 100%;
}

.context-field > input:focus,
.context-field > select:focus,
.context-new input:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
}

.context-field > button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.74rem;
  font-weight: 650;
  min-height: 2.5rem;
  padding: 0.4rem 0;
}

.context-field > .context-field__locate {
  align-items: center;
  display: inline-flex;
  gap: 0.35rem;
}

.context-field > button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.church-suggestions {
  border: 1px solid var(--color-margin);
  display: grid;
}

.church-suggestions button {
  align-items: center;
  background: var(--color-vellum);
  border: 0;
  border-bottom: 1px solid var(--color-margin);
  color: var(--color-ink);
  cursor: pointer;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.7rem 0.8rem;
  text-align: left;
}

.church-suggestions button:last-child {
  border-bottom: 0;
}

.church-suggestions span,
.church-suggestions strong,
.church-suggestions small {
  display: block;
}

.church-suggestions strong {
  font: 650 0.82rem var(--font-utility);
}

.church-suggestions small {
  color: var(--color-ink-muted);
  font: 0.7rem var(--font-utility);
  margin-top: 0.15rem;
}

.context-new {
  display: grid;
  gap: 0.5rem;
}

.context-new button,
.context-panel__footer button {
  background: var(--color-lapis);
  border: 1px solid var(--color-lapis);
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  min-height: 2.55rem;
  padding: 0.55rem 0.8rem;
}

.context-new button {
  justify-self: start;
}

.context-panel__footer {
  align-items: center;
  border-top: 1px solid var(--color-margin);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin-top: 1.5rem;
  padding-top: 1rem;
}

.context-panel__footer span,
.context-panel__status {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.76rem;
}

.context-new button:disabled,
.context-panel__footer button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.share-panel {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  margin: 1.5rem 0;
  padding: clamp(1.25rem, 4vw, 2rem);
}

.share-panel h2 {
  font-family: var(--font-display);
  font-size: clamp(1.65rem, 4vw, 2.25rem);
  font-variation-settings: 'opsz' 38, 'SOFT' 48;
  font-weight: 540;
  letter-spacing: -0.035em;
  margin: 0.35rem 0 0;
}

.share-panel > div:first-child > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.6;
  margin: 0.8rem 0 1.25rem;
  max-width: 44rem;
}

.share-panel input {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  padding: 0.8rem;
  width: 100%;
}

.share-panel input:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
}

.share-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.75rem;
}

.share-panel__actions button,
.share-panel__publish {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  gap: 0.4rem;
  min-height: 2.55rem;
  padding: 0.55rem 0.75rem;
}

.share-panel__publish {
  background: var(--color-lapis);
  color: var(--color-vellum-light);
}

.share-panel__actions button:last-child {
  border-color: var(--color-rubric);
  color: var(--color-rubric);
}

.share-panel__actions button:disabled,
.share-panel__publish:disabled {
  cursor: wait;
  opacity: 0.58;
}

.share-panel__status {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  margin: 0.8rem 0 0;
}

.audio-player {
  align-items: center;
  background: var(--color-ink);
  color: var(--color-vellum);
  display: grid;
  gap: 1rem;
  grid-template-columns: auto 1fr;
  margin: 1.5rem 0;
  padding: 1rem 1.15rem;
}

.audio-player__play {
  align-items: center;
  background: var(--color-vellum);
  border: 0;
  border-radius: 50%;
  color: var(--color-rubric);
  cursor: pointer;
  display: flex;
  height: 2.8rem;
  justify-content: center;
  padding-left: 0.15rem;
  width: 2.8rem;
}

.audio-player__labels {
  color: rgba(241, 238, 228, 0.72);
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.73rem;
  justify-content: space-between;
  margin-bottom: 0.55rem;
}

.audio-player__labels span:first-child {
  color: var(--color-vellum);
  font-weight: 650;
}

.audio-player__track {
  background: rgba(241, 238, 228, 0.17);
  height: 2px;
}

.audio-player__track span {
  background: var(--color-rule-gold);
  display: block;
  height: 100%;
  position: relative;
}

.audio-player__track span::after {
  background: var(--color-vellum);
  border-radius: 50%;
  content: '';
  height: 0.55rem;
  position: absolute;
  right: 0;
  top: 50%;
  transform: translate(50%, -50%);
  width: 0.55rem;
}

.audio-player__error {
  color: color-mix(in srgb, var(--color-vellum) 72%, var(--color-rubric));
  display: block;
  font-family: var(--font-utility);
  font-size: 0.7rem;
  margin-top: 0.65rem;
}

.section-tabs {
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  gap: clamp(0.2rem, 3vw, 1.5rem);
  margin-bottom: 3rem;
  overflow-x: auto;
}

.section-tabs button {
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--color-ink-muted);
  cursor: pointer;
  flex: none;
  font-family: var(--font-utility);
  font-size: 0.8rem;
  font-weight: 650;
  letter-spacing: 0.06em;
  min-height: 3rem;
  padding: 0 0.5rem;
  text-transform: uppercase;
}

.section-tabs button.active {
  border-bottom-color: var(--color-rubric);
  color: var(--color-rubric);
}

.edit-message {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  margin: -2rem auto 2rem;
  max-width: var(--reading-width);
}

.sermon-content {
  margin: 0 auto;
  max-width: var(--reading-width);
}

.artifact {
  border-bottom: 1px solid var(--color-margin);
  padding: 0 0 3rem;
}

.artifact + .artifact {
  padding-top: 3rem;
}

.artifact__heading {
  align-items: start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.artifact h2 {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 4vw, 2.3rem);
  font-variation-settings: 'opsz' 38, 'SOFT' 48;
  font-weight: 540;
  letter-spacing: -0.03em;
  line-height: 1.08;
  margin: 0;
}

.artifact__edit {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-ink-muted);
  cursor: pointer;
  display: flex;
  flex: none;
  height: 2.5rem;
  justify-content: center;
  width: 2.5rem;
}

.artifact__edit:hover {
  color: var(--color-lapis);
}

.artifact-editor {
  margin-top: 1.25rem;
}

.artifact-editor textarea {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 1rem;
  line-height: 1.65;
  padding: 1rem;
  resize: vertical;
  width: 100%;
}

.artifact-editor textarea:focus {
  border-color: var(--color-lapis);
  box-shadow: 0 0 0 3px rgba(47, 75, 124, 0.11);
  outline: 0;
}

.artifact-editor__actions {
  display: flex;
  gap: 0.5rem;
  justify-content: end;
  margin-top: 0.6rem;
}

.artifact-editor__actions button {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-margin);
  color: var(--color-ink-muted);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  gap: 0.35rem;
  min-height: 2.5rem;
  padding: 0.5rem 0.75rem;
}

.artifact-editor__actions button:last-child {
  background: var(--color-lapis);
  border-color: var(--color-lapis);
  color: var(--color-vellum-light);
}

.artifact-editor__actions button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.artifact__summary {
  font-family: var(--font-reading);
  font-size: clamp(1.18rem, 3vw, 1.42rem);
  line-height: 1.6;
  margin: 1rem 0 0;
}

.artifact__prose {
  font-family: var(--font-reading);
  font-size: 1.02rem;
  line-height: 1.75;
  margin-top: 1.4rem;
}

.artifact__prose p + p {
  margin-top: 1rem;
}

.scripture-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  margin-top: 1.25rem;
}

.scripture-links a {
  align-items: center;
  border-bottom: 1px solid rgba(47, 75, 124, 0.4);
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-reading);
  font-size: 0.95rem;
  gap: 0.45rem;
  padding-bottom: 0.25rem;
  text-decoration: none;
}

.outline {
  counter-reset: outline;
  list-style: none;
  margin: 1.4rem 0 0;
  padding: 0;
}

.outline li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  counter-increment: outline;
  display: grid;
  font-family: var(--font-reading);
  gap: 1rem;
  grid-template-columns: 2rem 1fr;
  line-height: 1.5;
  padding: 0.9rem 0;
}

.outline li::before {
  color: var(--color-rubric);
  content: counter(outline, upper-roman);
  font-family: var(--font-display);
  font-size: 0.78rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1.25rem;
}

.tag-list span {
  background: transparent;
  border: 0;
  border-bottom: 1px solid rgba(47, 75, 124, 0.35);
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  padding: 0.3rem 0;
}

.related-sermons {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.related-sermons a {
  border-left: 2px solid var(--color-rule-gold);
  color: var(--color-ink);
  display: grid;
  gap: 0.2rem;
  padding: 0.75rem 1rem;
  text-decoration: none;
}

.related-sermons strong {
  font-family: var(--font-reading);
  font-size: 0.95rem;
}

.related-sermons span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
}

.transcript__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  line-height: 1.5;
  margin: 1rem 0 2.5rem;
}

.transcript-editor {
  display: grid;
  gap: 1rem;
}

.transcript-editor label {
  align-items: start;
  display: grid;
  gap: 1rem;
  grid-template-columns: 3.2rem 1fr;
}

.transcript-editor label > span {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  padding-top: 0.7rem;
}

.transcript-editor textarea {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 0.95rem;
  line-height: 1.55;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  width: 100%;
}

.transcript-editor textarea:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
}

.transcript__segment {
  align-items: baseline;
  display: grid;
  gap: 1rem;
  grid-template-columns: 3.2rem 1fr;
}

.transcript__segment + .transcript__segment {
  margin-top: 1.45rem;
}

.transcript__segment button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  padding: 0.25rem 0;
}

.transcript__segment p {
  font-family: var(--font-reading);
  font-size: 1.07rem;
  line-height: 1.72;
  margin: 0;
}

.question-set > h2 {
  margin-top: 0.5rem;
}

.question-set ol {
  list-style: none;
  margin: 2rem 0 0;
  padding: 0;
}

.question-set li {
  border-top: 1px solid var(--color-margin);
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.6;
  padding: 1.1rem 0;
}

.question-set--kids {
  background: rgba(47, 75, 124, 0.055);
  border-bottom: 0;
  margin-top: 2.5rem;
  padding: 2rem;
}

.reflection__prompt {
  color: var(--color-lapis);
  font-family: var(--font-reading);
  font-size: 1.08rem;
  font-style: italic;
  line-height: 1.55;
  margin: 1.3rem 0 1rem;
}

.reflection textarea {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 1rem;
  line-height: 1.75;
  padding: 1.25rem;
  resize: vertical;
  width: 100%;
}

.reflection textarea:focus {
  border-color: var(--color-lapis);
  box-shadow: 0 0 0 3px rgba(47, 75, 124, 0.11);
  outline: 0;
}

.reflection__footer {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-top: 0.75rem;
}

.reflection__footer span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
}

.reflection__footer button {
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  min-height: 2.75rem;
  padding: 0.65rem 1rem;
}

.reflection__footer button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 600px) {
  .sermon-detail {
    padding-top: 1.25rem;
  }

  .back-link {
    margin-bottom: 1.6rem;
  }

  .sermon-header h1 {
    font-size: clamp(2.9rem, 14vw, 4.3rem);
  }

  .context-fields {
    grid-template-columns: 1fr;
  }

  .context-panel__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .section-tabs {
    margin-inline: -0.4rem;
  }

  .section-tabs button {
    font-size: 0.72rem;
  }

  .question-set--kids {
    margin-inline: -0.75rem;
    padding: 1.5rem 0.75rem;
  }
}
</style>
