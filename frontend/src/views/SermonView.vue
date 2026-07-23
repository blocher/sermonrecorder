<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
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
  Plus,
  RotateCcw,
  Share2,
  Trash2,
  UserRound,
  X,
} from '@lucide/vue'
import ReflectionEditor from '../components/ReflectionEditor.vue'
import { useAuth } from '../auth/useAuth'
import { findNearbyChurches } from '../location/findNearbyChurches'
import {
  createChurch,
  createPreacher,
  createShareLink,
  deleteSermon,
  loadChurches,
  loadPreachers,
  loadShareLink,
  loadServerSermon,
  retrySermonProcessing,
  revokeShareLink,
  saveReflection,
  serverSermonDuration,
  serverSermonTitle,
  updateStudyArtifact,
  updateSermonContext,
  updateScriptureReferences,
  updateTags,
  updateTranscript,
  type OccasionKind,
  type ChurchSuggestion,
  type ServerChurch,
  type ServerPreacher,
  type ServerShareLink,
  type ServerSermonDetail,
  type ServerScriptureReference,
  type ServerTranscriptSegment,
  type StudyArtifactKind,
} from '../sermons/serverSermon'

type Section = 'study' | 'transcript' | 'discuss' | 'reflection'
type TranscriptView = 'timeline' | 'reading'
type ScriptureReferenceDraft = Omit<
  ServerScriptureReference,
  'display' | 'chapter_start' | 'verse_start' | 'chapter_end' | 'verse_end'
> & {
  chapter_start: number | ''
  verse_start: number | ''
  chapter_end: number | ''
  verse_end: number | ''
}

const route = useRoute()
const router = useRouter()
const { isAuthenticated } = useAuth()
const sermon = ref<ServerSermonDetail>()
const processingSermon = ref<ServerSermonDetail>()
const sectionTabs = ref<HTMLElement>()
const loading = ref(true)
const errorMessage = ref('')
const failedSermonId = ref('')
const retrying = ref(false)
const checkingProcessing = ref(false)
const activeSection = ref<Section>('study')
const transcriptView = ref<TranscriptView>('timeline')
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
const editingTags = ref(false)
const tagEdits = ref<string[]>([])
const newTag = ref('')
const savingTags = ref(false)
const tagMessage = ref('')
const editingScripture = ref(false)
const scriptureEdits = ref<ScriptureReferenceDraft[]>([])
const savingScripture = ref(false)
const scriptureMessage = ref('')
const reflectionPrompt = 'Where is this sermon asking for one faithful action?'
const reflectionContent = ref('')
const savingReflection = ref(false)
const reflectionMessage = ref('')
const sharePanelOpen = ref(false)
const shareLink = ref<ServerShareLink | null>(null)
const shareLoading = ref(false)
const shareBusy = ref(false)
const shareMessage = ref('')
const confirmingDelete = ref(false)
const deleting = ref(false)
const deleteMessage = ref('')
const contextPanelOpen = ref(false)
const contextLoading = ref(false)
const contextSaving = ref(false)
const contextMessage = ref('')
const churches = ref<ServerChurch[]>([])
const preachers = ref<ServerPreacher[]>([])
const sermonTitle = ref('')
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
let processingPollTimer: ReturnType<typeof setTimeout> | undefined

const progress = computed(() =>
  sermon.value ? Math.min(currentSeconds.value / sermon.value.duration_seconds, 1) : 0,
)
const progressLabel = computed(() => `${Math.round(progress.value * 100)}%`)
const readingTranscriptParagraphs = computed(() => {
  const segments = sermon.value?.transcript?.segments ?? []
  if (!segments.length) {
    const text = sermon.value?.transcript?.text.trim()
    return text ? paragraphs(text) : []
  }

  const grouped: string[] = []
  let paragraph = ''
  let wordCount = 0
  for (const segment of segments) {
    const text = segment.text.trim()
    if (!text) continue
    paragraph = `${paragraph} ${text}`.trim()
    wordCount += text.split(/\s+/).length
    if (wordCount >= 100) {
      grouped.push(paragraph)
      paragraph = ''
      wordCount = 0
    }
  }
  if (paragraph) grouped.push(paragraph)
  return grouped
})
const capturedDate = computed(() =>
  sermon.value
    ? new Intl.DateTimeFormat(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      }).format(new Date(sermon.value.captured_at))
    : '',
)
const capturedTime = computed(() =>
  sermon.value
    ? new Intl.DateTimeFormat(undefined, {
        hour: 'numeric',
        minute: '2-digit',
      }).format(new Date(sermon.value.captured_at))
    : '',
)
const processingCapturedDate = computed(() =>
  processingSermon.value
    ? new Intl.DateTimeFormat(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      }).format(new Date(processingSermon.value.captured_at))
    : '',
)
const occasionOptions: [OccasionKind, string][] = [
  ['sunday', 'Sunday'],
  ['feast', 'Feast or holy day'],
  ['wedding', 'Wedding'],
  ['funeral', 'Funeral'],
  ['midweek', 'Midweek service'],
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

function quotationItems(content: string): string[] {
  const quotePairs = new Set(['""', '“”', '‘’'])
  return content
    .split(/\n+/)
    .map((item) => item.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim())
    .map((item) =>
      item.length >= 2 && quotePairs.has(`${item[0]}${item.at(-1)}`)
        ? item.slice(1, -1).trim()
        : item,
    )
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

function beginTagEdit(): void {
  tagEdits.value = [...(sermon.value?.tag_suggestions ?? [])]
  newTag.value = ''
  tagMessage.value = ''
  editingTags.value = true
}

function cancelTagEdit(): void {
  tagEdits.value = []
  newTag.value = ''
  tagMessage.value = ''
  editingTags.value = false
}

function addTagEdit(): void {
  const tag = newTag.value.trim().replace(/\s+/g, ' ')
  if (!tag) return
  if (tagEdits.value.length >= 12) {
    tagMessage.value = 'A Sermon can have up to 12 Tags.'
    return
  }
  if (
    tagEdits.value.some(
      (existing) => existing.toLocaleLowerCase() === tag.toLocaleLowerCase(),
    )
  ) {
    tagMessage.value = 'That Tag is already here.'
    return
  }
  tagEdits.value.push(tag)
  newTag.value = ''
  tagMessage.value = ''
}

function removeTagEdit(index: number): void {
  tagEdits.value.splice(index, 1)
  tagMessage.value = ''
}

async function saveTagEdit(): Promise<void> {
  if (!sermon.value || savingTags.value) return
  savingTags.value = true
  tagMessage.value = ''
  try {
    sermon.value.tag_suggestions = await updateTags(sermon.value.id, tagEdits.value)
    editingTags.value = false
    tagMessage.value = 'Tags saved to this Sermon.'
  } catch (error) {
    tagMessage.value = error instanceof Error ? error.message : 'Your Tags could not be saved.'
  } finally {
    savingTags.value = false
  }
}

function beginScriptureEdit(): void {
  scriptureEdits.value = (sermon.value?.scripture_references ?? []).map(
    (reference) => ({
      book: reference.book,
      chapter_start: reference.chapter_start,
      verse_start: reference.verse_start ?? '',
      chapter_end: reference.chapter_end ?? '',
      verse_end: reference.verse_end ?? '',
    }),
  )
  scriptureMessage.value = ''
  editingScripture.value = true
}

function cancelScriptureEdit(): void {
  scriptureEdits.value = []
  scriptureMessage.value = ''
  editingScripture.value = false
}

function addScriptureEdit(): void {
  if (scriptureEdits.value.length >= 20) {
    scriptureMessage.value = 'A Sermon can have up to 20 Scripture references.'
    return
  }
  scriptureEdits.value.push({
    book: '',
    chapter_start: '',
    verse_start: '',
    chapter_end: '',
    verse_end: '',
  })
  scriptureMessage.value = ''
}

function removeScriptureEdit(index: number): void {
  scriptureEdits.value.splice(index, 1)
  scriptureMessage.value = ''
}

async function saveScriptureEdit(): Promise<void> {
  if (!sermon.value || savingScripture.value) return
  if (
    scriptureEdits.value.some(
      (reference) => !reference.book.trim() || reference.chapter_start === '',
    )
  ) {
    scriptureMessage.value = 'Each reference needs a book and starting chapter.'
    return
  }
  savingScripture.value = true
  scriptureMessage.value = ''
  try {
    sermon.value.scripture_references = await updateScriptureReferences(
      sermon.value.id,
      scriptureEdits.value.map((reference) => ({
        book: reference.book.trim().replace(/\s+/g, ' '),
        chapter_start: reference.chapter_start as number,
        verse_start: reference.verse_start === '' ? null : reference.verse_start,
        chapter_end: reference.chapter_end === '' ? null : reference.chapter_end,
        verse_end: reference.verse_end === '' ? null : reference.verse_end,
      })),
    )
    editingScripture.value = false
    scriptureMessage.value = 'Scripture references saved.'
  } catch (error) {
    scriptureMessage.value =
      error instanceof Error ? error.message : 'Your Scripture references could not be saved.'
  } finally {
    savingScripture.value = false
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

async function selectSection(section: Section): Promise<void> {
  activeSection.value = section
  await nextTick()
  sectionTabs.value?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'start',
  })
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
  if (!sharePanelOpen.value && contextPanelOpen.value) {
    contextMessage.value = 'Save or close the Sermon details before opening sharing.'
    return
  }
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
  if (contextPanelOpen.value) sharePanelOpen.value = false
  contextMessage.value = ''
  churchSuggestions.value = []
  if (!contextPanelOpen.value || !sermon.value) return
  sermonTitle.value = sermon.value.title
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

function beginDeleteConfirmation(): void {
  sharePanelOpen.value = false
  confirmingDelete.value = true
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
      ? 'Choose a Church near your current location to add it to your private place book.'
      : 'No Churches were found near your current location. You can still add one manually.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error
        ? error.message
        : 'Churches near your current location could not be suggested.'
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
      latitude: suggestion.latitude.toFixed(6),
      longitude: suggestion.longitude.toFixed(6),
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
      title: sermonTitle.value,
      church_id: selectedChurchId.value || null,
      preacher_id: selectedPreacherId.value || null,
      occasion_kind: selectedOccasionKind.value,
      liturgical_day: liturgicalDay.value,
    })
    sermon.value.title = saved.title
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

function clearProcessingPoll(): void {
  if (processingPollTimer !== undefined) {
    window.clearTimeout(processingPollTimer)
    processingPollTimer = undefined
  }
}

function scheduleProcessingPoll(id: string): void {
  clearProcessingPoll()
  processingPollTimer = window.setTimeout(() => void refreshProcessing(id), 5000)
}

function applyLoadedSermon(loadedSermon: ServerSermonDetail, id: string): void {
  clearProcessingPoll()
  errorMessage.value = ''
  failedSermonId.value = ''

  if (loadedSermon.processing_status === 'ready') {
    processingSermon.value = undefined
    sermon.value = loadedSermon
    reflectionContent.value = loadedSermon.reflections[0]?.content ?? ''
    return
  }

  sermon.value = undefined
  processingSermon.value = loadedSermon
  if (loadedSermon.processing_status === 'failed') {
    failedSermonId.value = loadedSermon.id
  } else {
    scheduleProcessingPoll(id)
  }
}

async function refreshProcessing(id: string, manual = false): Promise<void> {
  if (String(route.params.id) !== id) return
  if (manual) checkingProcessing.value = true
  try {
    const loadedSermon = await loadServerSermon(id)
    if (String(route.params.id) === id) applyLoadedSermon(loadedSermon, id)
  } catch {
    if (
      String(route.params.id) === id &&
      processingSermon.value?.processing_status !== 'failed'
    ) {
      scheduleProcessingPoll(id)
    }
  } finally {
    if (manual) checkingProcessing.value = false
  }
}

async function load(id: string): Promise<void> {
  clearProcessingPoll()
  loading.value = true
  errorMessage.value = ''
  failedSermonId.value = ''
  sermon.value = undefined
  processingSermon.value = undefined
  editingKind.value = undefined
  editMessage.value = ''
  editingTags.value = false
  tagEdits.value = []
  newTag.value = ''
  tagMessage.value = ''
  editingScripture.value = false
  scriptureEdits.value = []
  scriptureMessage.value = ''
  reflectionMessage.value = ''
  sharePanelOpen.value = false
  shareLink.value = null
  shareMessage.value = ''
  confirmingDelete.value = false
  deleteMessage.value = ''
  contextPanelOpen.value = false
  contextMessage.value = ''
  try {
    const loadedSermon = await loadServerSermon(id)
    applyLoadedSermon(loadedSermon, id)
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

async function retryFailedProcessing(): Promise<void> {
  if (!failedSermonId.value || retrying.value) return
  retrying.value = true
  try {
    const retried = await retrySermonProcessing(failedSermonId.value)
    if (processingSermon.value) {
      processingSermon.value = { ...processingSermon.value, ...retried }
    }
    failedSermonId.value = ''
    scheduleProcessingPoll(retried.id)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'This Sermon could not be retried.'
  } finally {
    retrying.value = false
  }
}

async function deleteCurrentSermon(): Promise<void> {
  if (!sermon.value || deleting.value) return
  deleting.value = true
  deleteMessage.value = ''
  try {
    audio.value?.pause()
    await deleteSermon(sermon.value.id)
    await router.replace('/')
  } catch (error) {
    deleteMessage.value =
      error instanceof Error ? error.message : 'This Sermon could not be deleted.'
  } finally {
    deleting.value = false
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

onBeforeUnmount(clearProcessingPoll)
</script>

<template>
  <main class="sermon-detail page-gather">
    <button class="back-link" type="button" @click="router.push('/')">
      <ArrowLeft :size="17" :stroke-width="1.7" aria-hidden="true" />
      Library
    </button>

    <p v-if="loading" class="detail-state" role="status">Opening your Sermon…</p>
    <section
      v-else-if="processingSermon && processingSermon.processing_status !== 'failed'"
      class="detail-state detail-state--processing"
      role="status"
      aria-live="polite"
    >
      <p class="detail-state__status">
        <span class="detail-state__pulse" aria-hidden="true"></span>
        Preparing your Sermon
      </p>
      <h1>{{ serverSermonTitle(processingSermon) }}</h1>
      <div class="detail-state__meta">
        <span>{{ processingCapturedDate }}</span>
        <span>{{ serverSermonDuration(processingSermon.duration_seconds) }}</span>
      </div>
      <p class="detail-state__body">{{ processingSermon.processing_message }}</p>
      <p class="detail-state__note">
        We’re creating the Transcript, title, and study notes. You can leave this page and check
        back soon—it will update automatically while it’s open.
      </p>
      <button
        class="detail-state__retry"
        type="button"
        :disabled="checkingProcessing"
        @click="refreshProcessing(processingSermon.id, true)"
      >
        <RotateCcw
          :class="{ 'is-spinning': checkingProcessing }"
          :size="16"
          aria-hidden="true"
        />
        {{ checkingProcessing ? 'Checking…' : 'Check now' }}
      </button>
    </section>
    <section
      v-else-if="processingSermon?.processing_status === 'failed'"
      class="detail-state detail-state--error"
      role="alert"
    >
      <p class="rubric-label">Needs attention</p>
      <h1>Processing couldn’t finish</h1>
      <p class="detail-state__body">
        {{ errorMessage || processingSermon.processing_message }}
      </p>
      <button
        class="detail-state__retry"
        type="button"
        :disabled="retrying"
        @click="retryFailedProcessing"
      >
        <RotateCcw :size="16" aria-hidden="true" />
        {{ retrying ? 'Retrying…' : 'Try again' }}
      </button>
    </section>
    <section v-else-if="errorMessage" class="detail-state detail-state--error" role="alert">
      <p class="rubric-label">Unable to open</p>
      <h1>This Sermon isn’t available</h1>
      <p class="detail-state__body">{{ errorMessage }}</p>
    </section>

    <article v-else-if="sermon">
      <header class="sermon-header">
        <div class="sermon-header__rubric">
          <span>{{ sermon.liturgical_day || 'Pew recording' }}</span>
          <span v-if="sermon.occasion_kind">{{ occasionLabel(sermon.occasion_kind) }}</span>
          <span>Ready</span>
        </div>
        <h1>{{ serverSermonTitle(sermon) }}</h1>
        <dl class="sermon-register" aria-label="Sermon details">
          <div class="sermon-register__entry">
            <dt><MapPin :size="15" aria-hidden="true" />Church</dt>
            <dd>
              <strong :class="{ 'is-unset': !sermon.church }">{{
                sermon.church?.name || 'Not assigned'
              }}</strong>
              <small v-if="sermon.church?.address">{{ sermon.church.address }}</small>
              <small v-else-if="!sermon.church">Add the Church when you know it</small>
            </dd>
          </div>
          <div class="sermon-register__entry">
            <dt><UserRound :size="15" aria-hidden="true" />Preacher</dt>
            <dd>
              <strong :class="{ 'is-unset': !sermon.preacher }">{{
                sermon.preacher?.name || 'Not assigned'
              }}</strong>
            </dd>
          </div>
          <div class="sermon-register__entry">
            <dt><BookOpenText :size="15" aria-hidden="true" />Occasion</dt>
            <dd>
              <strong :class="{ 'is-unset': !sermon.occasion_kind }">
                {{ occasionLabel(sermon.occasion_kind) || 'Not specified' }}
              </strong>
            </dd>
          </div>
          <div class="sermon-register__entry">
            <dt><CalendarDays :size="15" aria-hidden="true" />Heard</dt>
            <dd>
              <strong>{{ capturedDate }}</strong>
              <small>{{ capturedTime }}</small>
            </dd>
          </div>
          <div class="sermon-register__entry">
            <dt><Clock3 :size="15" aria-hidden="true" />Length</dt>
            <dd>
              <strong>{{ serverSermonDuration(sermon.duration_seconds) }}</strong>
            </dd>
          </div>
        </dl>
        <div class="sermon-header__actions">
          <button type="button" @click="toggleContextPanel">
            <PencilLine :size="16" aria-hidden="true" />
            {{ contextPanelOpen ? 'Close details' : 'Edit details' }}
          </button>
          <button
            type="button"
            :disabled="contextPanelOpen"
            :title="contextPanelOpen ? 'Save or close details before sharing' : undefined"
            @click="toggleSharePanel"
          >
            <Share2 :size="16" aria-hidden="true" />
            {{ sharePanelOpen ? 'Close sharing' : 'Share Sermon' }}
          </button>
          <button type="button" @click="router.push(`/sermons/${sermon.id}/email`)">
            <Mail :size="16" aria-hidden="true" />
            Email handout
          </button>
          <button
            v-if="!confirmingDelete"
            class="sermon-header__delete"
            type="button"
            :disabled="deleting"
            @click="beginDeleteConfirmation"
          >
            <Trash2 :size="16" aria-hidden="true" />
            Delete Sermon
          </button>
        </div>
      </header>

      <section
        v-if="confirmingDelete"
        class="sermon-delete-confirm"
        aria-labelledby="delete-sermon-title"
      >
        <div>
          <p class="rubric-label">Permanent deletion</p>
          <h2 id="delete-sermon-title">Delete this Sermon?</h2>
          <p>
            This removes the recording, Transcript, Study artifacts, Reflections, and any active
            Share link. It cannot be undone.
          </p>
          <p v-if="deleteMessage" class="sermon-delete-confirm__error" role="alert">
            {{ deleteMessage }}
          </p>
        </div>
        <div class="sermon-delete-confirm__actions">
          <button type="button" :disabled="deleting" @click="confirmingDelete = false">
            Keep Sermon
          </button>
          <button
            class="sermon-delete-confirm__delete"
            type="button"
            :disabled="deleting"
            @click="deleteCurrentSermon"
          >
            {{ deleting ? 'Deleting…' : 'Delete permanently' }}
          </button>
        </div>
      </section>

      <section v-if="contextPanelOpen" class="context-panel" aria-label="Sermon details">
        <div class="context-panel__heading">
          <p class="rubric-label">Sermon details</p>
          <h2>Make this Sermon easy to return to</h2>
          <p>
            New Sermons begin with an AI-suggested title. Change it whenever you like, and reuse
            Churches and Preachers from your private books.
          </p>
        </div>
        <p v-if="contextLoading" class="context-panel__status" role="status">
          Opening your saved details…
        </p>
        <div v-else class="context-fields">
          <div class="context-field context-field--wide">
            <label for="sermon-title">Title</label>
            <input
              id="sermon-title"
              v-model="sermonTitle"
              type="text"
              maxlength="160"
              placeholder="Add a memorable title"
            />
            <small>
              {{ sermonTitle.length }}/160 ·
              {{
                sermon.title
                  ? 'You can replace the AI suggestion.'
                  : 'This older Sermon has no suggested title yet.'
              }}
            </small>
          </div>

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
              {{ findingChurches ? 'Finding near me…' : 'Find Churches near me' }}
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
          <div
            class="audio-player__track"
            role="progressbar"
            aria-label="Sermon playback progress"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="Math.round(progress * 100)"
          >
            <span :style="{ width: progressLabel }"></span>
          </div>
          <small v-if="playbackError" class="audio-player__error">
            Audio could not be played. Reopen this Sermon to refresh its private link.
          </small>
        </div>
      </section>

      <nav ref="sectionTabs" class="section-tabs" aria-label="Sermon sections">
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
          :aria-pressed="activeSection === section[0]"
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

          <section v-if="artifact('quotations')" class="artifact artifact--quotations">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">In the preacher’s words</p>
                <h2>Quotations</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit Quotations"
                @click="beginArtifactEdit('quotations')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'quotations'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="8"
                aria-label="Quotations, one per line"
              ></textarea>
              <p class="artifact-editor__hint">Keep one word-for-word quotation on each line.</p>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <div v-else class="quotation-list">
              <blockquote v-for="quotation in quotationItems(artifact('quotations'))" :key="quotation">
                <p>{{ quotation }}</p>
              </blockquote>
            </div>
          </section>

          <section v-if="artifact('call_to_action')" class="artifact artifact--call">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">One next action</p>
                <h2>Carry this with you</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit one next action"
                @click="beginArtifactEdit('call_to_action')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'call_to_action'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="3"
                maxlength="240"
                aria-label="One next action"
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
            <p v-else class="artifact__call">{{ artifact('call_to_action') }}</p>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Scripture</h2>
              <button
                v-if="!editingScripture"
                class="artifact__edit"
                type="button"
                aria-label="Edit Scripture references"
                @click="beginScriptureEdit"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingScripture" class="scripture-editor">
              <div
                v-for="(reference, index) in scriptureEdits"
                :key="index"
                class="scripture-editor__row"
              >
                <label class="scripture-editor__book">
                  <span>Book</span>
                  <input v-model="reference.book" maxlength="64" placeholder="Luke" />
                </label>
                <label>
                  <span>Chapter</span>
                  <input
                    v-model.number="reference.chapter_start"
                    type="number"
                    min="1"
                    max="32767"
                    inputmode="numeric"
                  />
                </label>
                <label>
                  <span>Verse</span>
                  <input
                    v-model.number="reference.verse_start"
                    type="number"
                    min="1"
                    max="32767"
                    inputmode="numeric"
                    placeholder="—"
                  />
                </label>
                <label>
                  <span>Through chapter</span>
                  <input
                    v-model.number="reference.chapter_end"
                    type="number"
                    min="1"
                    max="32767"
                    inputmode="numeric"
                    placeholder="—"
                  />
                </label>
                <label>
                  <span>Through verse</span>
                  <input
                    v-model.number="reference.verse_end"
                    type="number"
                    min="1"
                    max="32767"
                    inputmode="numeric"
                    placeholder="—"
                  />
                </label>
                <button
                  class="scripture-editor__remove"
                  type="button"
                  :aria-label="`Remove Scripture reference ${index + 1}`"
                  @click="removeScriptureEdit(index)"
                >
                  <Trash2 :size="16" aria-hidden="true" />
                </button>
              </div>
              <button
                class="scripture-editor__add"
                type="button"
                :disabled="scriptureEdits.length >= 20"
                @click="addScriptureEdit"
              >
                <Plus :size="15" aria-hidden="true" /> Add reference
              </button>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelScriptureEdit">
                  <X :size="15" /> Cancel
                </button>
                <button
                  type="button"
                  :disabled="savingScripture"
                  @click="saveScriptureEdit"
                >
                  <Check :size="15" />{{ savingScripture ? 'Saving…' : 'Save references' }}
                </button>
              </div>
            </div>
            <div v-else-if="sermon.scripture_references.length" class="scripture-links">
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
            <p v-else class="scripture-links__empty">No Scripture references saved yet.</p>
            <p v-if="scriptureMessage" class="artifact__message" role="status">
              {{ scriptureMessage }}
            </p>
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

          <section v-if="artifact('practical_next_steps')" class="artifact">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Put it into practice</p>
                <h2>Practical next steps</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit practical next steps"
                @click="beginArtifactEdit('practical_next_steps')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'practical_next_steps'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="8"
                aria-label="Practical next steps"
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
            <ol v-else class="practical-steps">
              <li v-for="step in numberedItems(artifact('practical_next_steps'))" :key="step">
                {{ step }}
              </li>
            </ol>
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
              <button
                v-if="!editingTags"
                class="artifact__edit"
                type="button"
                aria-label="Edit Tags"
                @click="beginTagEdit"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingTags" class="tag-editor">
              <div class="tag-editor__list">
                <span v-for="(tag, index) in tagEdits" :key="`${tag}-${index}`">
                  {{ tag }}
                  <button
                    type="button"
                    :aria-label="`Remove ${tag}`"
                    @click="removeTagEdit(index)"
                  >
                    <X :size="13" aria-hidden="true" />
                  </button>
                </span>
              </div>
              <div class="tag-editor__add">
                <input
                  v-model="newTag"
                  maxlength="80"
                  placeholder="Add a Tag"
                  aria-label="New Tag"
                  @keydown.enter.prevent="addTagEdit"
                />
                <button
                  type="button"
                  :disabled="!newTag.trim() || tagEdits.length >= 12"
                  @click="addTagEdit"
                >
                  <Plus :size="15" aria-hidden="true" /> Add
                </button>
              </div>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelTagEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingTags" @click="saveTagEdit">
                  <Check :size="15" />{{ savingTags ? 'Saving…' : 'Save Tags' }}
                </button>
              </div>
            </div>
            <div v-else-if="sermon.tag_suggestions.length" class="tag-list">
              <RouterLink
                v-for="tag in sermon.tag_suggestions"
                :key="tag"
                :to="{ path: '/', query: { tag } }"
                :aria-label="`Show Sermons tagged ${tag}`"
              >
                {{ tag }}
              </RouterLink>
            </div>
            <p v-else class="tag-list__empty">No Tags saved yet.</p>
            <p v-if="tagMessage" class="artifact__message" role="status">
              {{ tagMessage }}
            </p>
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
            <div class="transcript-view-toggle" role="group" aria-label="Transcript view">
              <button
                type="button"
                :class="{ active: transcriptView === 'timeline' }"
                :aria-pressed="transcriptView === 'timeline'"
                @click="transcriptView = 'timeline'"
              >
                Timeline
              </button>
              <button
                type="button"
                :class="{ active: transcriptView === 'reading' }"
                :aria-pressed="transcriptView === 'reading'"
                @click="transcriptView = 'reading'"
              >
                Reading
              </button>
            </div>
            <p class="transcript__note">
              {{
                transcriptView === 'timeline'
                  ? 'Side conversations have been removed. Tap a timestamp to listen from that moment.'
                  : 'The cleaned Transcript is gathered into longer paragraphs for uninterrupted reading.'
              }}
            </p>
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
            <div v-else-if="transcriptView === 'timeline'" class="transcript__segments">
              <div
                v-for="segment in sermon.transcript?.segments ?? []"
                :key="`${segment.start_seconds}-${segment.text}`"
                class="transcript__segment"
              >
                <button
                  type="button"
                  :aria-label="`Play from ${timestamp(segment.start_seconds)}`"
                  @click="seekTo(segment.start_seconds)"
                >
                  {{ timestamp(segment.start_seconds) }}
                </button>
                <p>{{ segment.text }}</p>
              </div>
            </div>
            <div v-else class="transcript__reading">
              <p v-for="(paragraph, index) in readingTranscriptParagraphs" :key="index">
                {{ paragraph }}
              </p>
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
            <ReflectionEditor
              v-model="reflectionContent"
              :prompt="reflectionPrompt"
              :saving="savingReflection"
              :message="reflectionMessage"
              @save="persistReflection"
            />
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

.detail-state--processing {
  background: color-mix(in srgb, var(--color-vellum-light) 70%, transparent);
  border-bottom: 1px solid var(--color-rule-gold);
  border-top: 1px solid var(--color-rule-gold);
  margin-top: 1.5rem;
  padding: clamp(2.5rem, 8vw, 5rem) clamp(1.25rem, 6vw, 4rem);
}

.detail-state h1 {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 7vw, 4.5rem);
  font-weight: 520;
  letter-spacing: -0.05em;
  line-height: 0.98;
  margin: 0.75rem 0 0;
  max-width: 16ch;
}

.detail-state__status {
  align-items: center;
  color: var(--color-rubric);
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  gap: 0.55rem;
  letter-spacing: 0.11em;
  margin: 0;
  text-transform: uppercase;
}

.detail-state__pulse {
  background: var(--color-rubric);
  border-radius: 50%;
  display: inline-block;
  height: 0.55rem;
  width: 0.55rem;
  animation: processing-pulse 1.8s ease-in-out infinite;
}

.detail-state__meta {
  color: var(--color-ink-muted);
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  gap: 1.2rem;
  margin-top: 1.1rem;
}

.detail-state__meta span + span::before {
  color: var(--color-rule-gold);
  content: '·';
  margin-right: 1.2rem;
}

.detail-state__body {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.55;
  margin-top: 1rem;
  max-width: 36rem;
}

.detail-state__note {
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.65;
  margin: 1.25rem 0 0;
  max-width: 38rem;
}

.detail-state__retry {
  align-items: center;
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--color-lapis) 40%, transparent);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 700;
  gap: 0.45rem;
  margin-top: 1.5rem;
  min-height: 2.75rem;
  padding: 0.65rem 1rem;
}

.detail-state__retry:disabled {
  cursor: wait;
  opacity: 0.65;
}

.detail-state__retry .is-spinning {
  animation: processing-spin 0.9s linear infinite;
}

@keyframes processing-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-rubric) 35%, transparent);
  }
  50% {
    box-shadow: 0 0 0 0.4rem transparent;
  }
}

@keyframes processing-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .detail-state__pulse,
  .detail-state__retry .is-spinning {
    animation: none;
  }
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
  max-width: 18ch;
}

.sermon-register {
  background: color-mix(in srgb, var(--color-vellum-light) 82%, transparent);
  border-bottom: 1px solid var(--color-rule-gold);
  border-top: 1px solid var(--color-rule-gold);
  display: grid;
  grid-template-columns: 1.35fr 1fr 1.2fr 1fr 0.7fr;
  margin: 2rem 0 0;
}

.sermon-register__entry {
  min-width: 0;
  padding: 1rem clamp(0.7rem, 2vw, 1.15rem);
}

.sermon-register__entry + .sermon-register__entry {
  border-left: 1px solid var(--color-margin);
}

.sermon-register dt {
  align-items: center;
  color: var(--color-rubric);
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.65rem;
  font-weight: 700;
  gap: 0.35rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sermon-register dd {
  margin: 0.55rem 0 0;
}

.sermon-register strong,
.sermon-register small {
  display: block;
  overflow-wrap: anywhere;
}

.sermon-register strong {
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.3;
}

.sermon-register strong.is-unset {
  color: var(--color-ink-muted);
  font-style: italic;
  font-weight: 400;
}

.sermon-register small {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.69rem;
  line-height: 1.35;
  margin-top: 0.25rem;
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

.sermon-header__actions .sermon-header__delete {
  border-color: color-mix(in srgb, var(--color-rubric) 55%, transparent);
  color: var(--color-rubric);
  margin-left: auto;
}

.sermon-header__actions button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.sermon-delete-confirm {
  align-items: end;
  background: color-mix(in srgb, var(--color-rubric) 5%, var(--color-vellum-light));
  border: 1px solid color-mix(in srgb, var(--color-rubric) 45%, var(--color-margin));
  display: flex;
  gap: 1.5rem;
  justify-content: space-between;
  margin: 1.5rem 0;
  padding: clamp(1.25rem, 4vw, 2rem);
}

.sermon-delete-confirm h2 {
  font-family: var(--font-display);
  font-size: clamp(1.65rem, 4vw, 2.25rem);
  font-weight: 540;
  letter-spacing: -0.035em;
  margin: 0.35rem 0 0;
}

.sermon-delete-confirm p:not(.rubric-label) {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.55;
  margin: 0.65rem 0 0;
  max-width: 44rem;
}

.sermon-delete-confirm__error {
  color: var(--color-rubric) !important;
}

.sermon-delete-confirm__actions {
  display: flex;
  flex: none;
  gap: 0.6rem;
}

.sermon-delete-confirm__actions button {
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  min-height: 2.65rem;
  padding: 0.55rem 0.8rem;
}

.sermon-delete-confirm__actions .sermon-delete-confirm__delete {
  background: var(--color-rubric);
  border-color: var(--color-rubric);
  color: var(--color-vellum-light);
}

.sermon-delete-confirm__actions button:disabled {
  cursor: wait;
  opacity: 0.6;
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

.context-field--wide {
  grid-column: 1 / -1;
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

.context-field--wide > input {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 540;
}

.context-field--wide > input::placeholder {
  color: color-mix(in srgb, var(--color-ink-muted) 70%, transparent);
  font-style: italic;
  font-weight: 400;
}

.context-field > small {
  color: var(--color-ink-muted);
  display: block;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  margin-top: 0.35rem;
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
  scroll-margin-top: calc(var(--header-height) + 1rem);
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

.artifact-editor__hint {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.74rem;
  margin: 0.35rem 0 0;
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

.quotation-list {
  display: grid;
  gap: 1.25rem;
  margin-top: 1.5rem;
}

.quotation-list blockquote {
  border-left: 2px solid var(--color-rule-gold);
  margin: 0;
  padding: 0.15rem 0 0.15rem clamp(1rem, 4vw, 1.6rem);
}

.quotation-list p {
  font-family: var(--font-reading);
  font-size: clamp(1.2rem, 3vw, 1.5rem);
  font-style: italic;
  line-height: 1.55;
  margin: 0;
}

.quotation-list p::before,
.quotation-list p::after {
  color: var(--color-rubric);
  font-family: var(--font-display);
  font-style: normal;
}

.quotation-list p::before {
  content: '“';
}

.quotation-list p::after {
  content: '”';
}

.artifact.artifact--call {
  background: color-mix(in srgb, var(--color-rule-gold) 11%, var(--color-vellum-light));
  border: 1px solid color-mix(in srgb, var(--color-rule-gold) 55%, var(--color-margin));
  padding: clamp(1.25rem, 4vw, 2rem);
}

.artifact--call + .artifact {
  padding-top: 3rem;
}

.artifact__call {
  font-family: var(--font-display);
  font-size: clamp(1.55rem, 4vw, 2.15rem);
  font-variation-settings: 'opsz' 38, 'SOFT' 48;
  letter-spacing: -0.025em;
  line-height: 1.25;
  margin: 1.1rem 0 0;
}

.practical-steps {
  display: grid;
  gap: 0.9rem;
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
}

.practical-steps li {
  border-left: 2px solid var(--color-rule-gold);
  font-family: var(--font-reading);
  font-size: 1.03rem;
  line-height: 1.6;
  padding: 0.4rem 0 0.4rem 1rem;
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

.scripture-links__empty {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-style: italic;
  margin: 1.25rem 0 0;
}

.scripture-editor {
  display: grid;
  gap: 1rem;
  margin-top: 1.25rem;
}

.scripture-editor__row {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  display: grid;
  gap: 0.7rem;
  grid-template-columns: 1fr 1fr;
  padding: 1rem;
  position: relative;
}

.scripture-editor__book {
  grid-column: 1 / -1;
  padding-right: 2rem;
}

.scripture-editor label span {
  color: var(--color-ink-muted);
  display: block;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 700;
  margin-bottom: 0.3rem;
}

.scripture-editor input {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-utility);
  min-height: 2.6rem;
  padding: 0.55rem 0.6rem;
  width: 100%;
}

.scripture-editor input:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
}

.scripture-editor__remove {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-rubric);
  cursor: pointer;
  display: inline-flex;
  padding: 0.25rem;
  position: absolute;
  right: 0.5rem;
  top: 0.5rem;
}

.scripture-editor__add {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-weight: 700;
  gap: 0.35rem;
  justify-self: start;
  padding: 0.55rem 0.8rem;
}

.scripture-editor__add:disabled {
  cursor: not-allowed;
  opacity: 0.45;
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

.tag-list a {
  background: transparent;
  border: 0;
  border-bottom: 1px solid rgba(47, 75, 124, 0.35);
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  padding: 0.3rem 0;
  text-decoration: none;
}

.tag-list a:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 3px;
}

.tag-list__empty {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-style: italic;
  margin: 1.25rem 0 0;
}

.tag-editor {
  display: grid;
  gap: 1rem;
  margin-top: 1.25rem;
}

.tag-editor__list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.tag-editor__list span {
  align-items: center;
  border: 1px solid var(--color-margin);
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  gap: 0.4rem;
  padding: 0.35rem 0.45rem 0.35rem 0.65rem;
}

.tag-editor__list button {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-rubric);
  cursor: pointer;
  display: inline-flex;
  padding: 0;
}

.tag-editor__add {
  display: flex;
  gap: 0.6rem;
}

.tag-editor__add input {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  flex: 1;
  font-family: var(--font-utility);
  min-width: 0;
  padding: 0.65rem 0.75rem;
}

.tag-editor__add input:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
}

.tag-editor__add button {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-weight: 700;
  gap: 0.35rem;
  padding: 0.55rem 0.8rem;
}

.tag-editor__add button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
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

.transcript-view-toggle {
  border: 1px solid var(--color-margin);
  display: inline-flex;
  margin-top: 1.25rem;
  padding: 0.2rem;
}

.transcript-view-toggle button {
  background: transparent;
  border: 0;
  color: var(--color-ink-muted);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.75rem;
  font-weight: 700;
  min-height: 2.25rem;
  padding: 0.4rem 0.8rem;
}

.transcript-view-toggle button.active {
  background: var(--color-lapis);
  color: var(--color-vellum-light);
}

.transcript-view-toggle button:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 2px;
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

.transcript__reading {
  font-family: var(--font-reading);
  font-size: clamp(1.06rem, 2vw, 1.17rem);
  line-height: 1.82;
}

.transcript__reading p {
  margin: 0;
}

.transcript__reading p + p {
  margin-top: 1.4rem;
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

@media (max-width: 800px) {
  .sermon-register {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .sermon-register__entry + .sermon-register__entry {
    border-left: 0;
  }

  .sermon-register__entry:nth-child(even) {
    border-left: 1px solid var(--color-margin);
  }

  .sermon-register__entry:nth-child(n + 3) {
    border-top: 1px solid var(--color-margin);
  }

  .sermon-register__entry:last-child {
    grid-column: 1 / -1;
  }
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

  .sermon-delete-confirm {
    align-items: stretch;
    flex-direction: column;
  }

  .sermon-header__actions .sermon-header__delete {
    margin-left: 0;
  }

  .sermon-delete-confirm__actions {
    flex-wrap: wrap;
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
