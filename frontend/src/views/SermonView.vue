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
  RefreshCw,
  RotateCcw,
  Share2,
  Trash2,
  UserRound,
  X,
} from '@lucide/vue'
import DoctrinalFindingsList from '../components/DoctrinalFindingsList.vue'
import ReflectionEditor from '../components/ReflectionEditor.vue'
import RelatedSourcesList from '../components/RelatedSourcesList.vue'
import SermonSectionTabs from '../components/SermonSectionTabs.vue'
import { useAuth } from '../auth/useAuth'
import { recordingCapturePlace } from '../location/recordingCapturePlace'
import {
  describeHtmlAudioError,
  isHtmlAudioAbortError,
  playHtmlAudio,
  prepareHtmlAudioBlobFallback,
  waitForHtmlAudioCanPlay,
} from '../playback/htmlAudio'
import { formatClock, parseClock, seekRatioFromClientX } from '../playback/seekTrack'
import {
  numberedItems,
  paragraphs,
  parseDoctrinalReview,
  parseHymn,
  parseOutlinePoints,
  parseQuiz,
  parseRelatedSources,
  parseTuneSuggestions,
  quotationItems,
} from '../sermons/artifactContent'
import type { SermonSection } from '../sermons/sections'
import {
  createChurch,
  createPreacher,
  createShareLink,
  deleteSermon,
  loadChurches,
  loadNearbyChurches,
  loadPreachers,
  loadShareLink,
  loadServerSermon,
  loadSermonAudioLinks,
  loadSermonStatus,
  loadStudyArtifacts,
  loadTranscript,
  regenerateMagisteriumSermon,
  regenerateSermon,
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
  type ServerSermonStatus,
  type ServerScriptureReference,
  type ServerTranscriptSegment,
  type StudyArtifactKind,
} from '../sermons/serverSermon'

type TranscriptLayout = 'timeline' | 'reading' | 'raw'
type TranscriptEdition = 'polished' | 'original'
type SermonActionsView = 'details' | 'share' | 'regenerate' | 'delete'
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
const sectionTabs = ref<InstanceType<typeof SermonSectionTabs>>()
const loading = ref(true)
const errorMessage = ref('')
const failedSermonId = ref('')
const retrying = ref(false)
const checkingProcessing = ref(false)
const loadingArtifacts = ref(false)
const loadingRawTranscript = ref(false)
const activeSection = ref<SermonSection>('study')
const transcriptLayout = ref<TranscriptLayout>('timeline')
const transcriptEdition = ref<TranscriptEdition>('polished')
const audio = ref<HTMLAudioElement>()
const playing = ref(false)
const currentSeconds = ref(0)
const playbackError = ref(false)
const playbackErrorDetail = ref('')
const preparingAudioFallback = ref(false)
const refreshingAudio = ref(false)
const audioReloadToken = ref(0)
type AudioVariant = 'playback' | 'isolated' | 'original'
const audioVariant = ref<AudioVariant>('playback')
let audioBlobUrl = ''
let audioFallbackGeneration = 0
let audioFallbackPromise: Promise<boolean> | undefined
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
const actionsView = ref<SermonActionsView | null>(null)
const actionsPanel = ref<HTMLElement>()
const shareLink = ref<ServerShareLink | null>(null)
const shareLoading = ref(false)
const shareBusy = ref(false)
const shareMessage = ref('')
const deleting = ref(false)
const deleteMessage = ref('')
const regenerating = ref(false)
const regeneratingMagisterium = ref(false)
const regenerateMessage = ref('')
const regenerateStartClock = ref('00:00')
const regenerateEndClock = ref('00:00')
const regenerateAudioSource = ref<'isolated' | 'original'>('original')
let magisteriumPollTimer: ReturnType<typeof setTimeout> | undefined
const scrubbing = ref(false)
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
const progressPercent = computed(() => `${Math.round(progress.value * 100)}%`)
const activeAudioUrl = computed(() => {
  const current = sermon.value
  if (!current) return ''
  if (audioVariant.value === 'original') return current.original_audio_url
  if (audioVariant.value === 'isolated') return current.isolated_audio_url || current.audio_url
  return current.playback_audio_url || current.audio_url
})
const hymn = computed(() => parseHymn(artifact('hymn')))
const hymnTunes = computed(() => parseTuneSuggestions(artifact('hymn_tune_suggestions')))
const quiz = computed(() => parseQuiz(artifact('quiz')))
const outlinePoints = computed(() => parseOutlinePoints(artifact('outline')))
const relatedSources = computed(() => parseRelatedSources(artifact('related_sources')))
const doctrinalReview = computed(() => parseDoctrinalReview(artifact('doctrinal_review')))
const actionsModalTitle = computed(() => {
  switch (actionsView.value) {
    case 'details':
      return 'Make this Sermon easy to return to'
    case 'share':
      return 'Share the sermon, never your Reflection'
    case 'regenerate':
      return 'Regenerate this Sermon?'
    case 'delete':
      return 'Delete this Sermon?'
    default:
      return ''
  }
})
const actionsModalRubric = computed(() => {
  switch (actionsView.value) {
    case 'details':
      return 'Sermon details'
    case 'share':
      return 'Unlisted page'
    case 'regenerate':
      return 'Destructive regeneration'
    case 'delete':
      return 'Permanent deletion'
    default:
      return ''
  }
})
const rawTranscriptSegments = computed(
  () => sermon.value?.transcript?.raw_segments ?? [],
)
const displayTranscriptSegments = computed(() => {
  const transcript = sermon.value?.transcript
  if (!transcript) return []
  return transcript.display_segments?.length
    ? transcript.display_segments
    : transcript.segments
})
const originalTranscriptSegments = computed(
  () => sermon.value?.transcript?.segments ?? [],
)

function readingParagraphsFromSegments(
  segments: { text: string }[],
  fallbackText = '',
): string[] {
  if (!segments.length) {
    const text = fallbackText.trim()
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
}

const cleanedReadingParagraphs = computed(() => {
  const transcript = sermon.value?.transcript
  return readingParagraphsFromSegments(
    displayTranscriptSegments.value,
    transcript?.display_text || transcript?.text || '',
  )
})
const originalReadingParagraphs = computed(() => {
  const transcript = sermon.value?.transcript
  return readingParagraphsFromSegments(
    originalTranscriptSegments.value,
    transcript?.text || '',
  )
})
const usingPolishedTranscript = computed(
  () => transcriptLayout.value !== 'raw' && transcriptEdition.value === 'polished',
)
const transcriptViewMeta = computed(() => {
  if (transcriptLayout.value === 'raw') {
    return {
      rubric: 'Full diarization',
      note: rawTranscriptSegments.value.length
        ? 'Every diarized segment, including side talk.'
        : 'Unavailable until the next regenerate on the current cleanup pipeline.',
    }
  }
  if (transcriptLayout.value === 'timeline') {
    return transcriptEdition.value === 'polished'
      ? {
          rubric: 'Polished for listening',
          note: 'Tap a timestamp to listen from that moment.',
        }
      : {
          rubric: 'As spoken',
          note: 'Side talk removed; wording left as transcribed. Tap a timestamp to listen.',
        }
  }
  return transcriptEdition.value === 'polished'
    ? {
        rubric: 'Polished for reading',
        note: 'Gathered into longer paragraphs for easier reading.',
      }
    : {
        rubric: 'As spoken',
        note: 'As transcribed, gathered into paragraphs for reading.',
      }
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
  const content =
    sermon.value?.study_artifacts.find((candidate) => candidate.kind === kind)?.content ?? ''
  if (content) return content
  // Shell payload includes short_summary before study artifacts hydrate.
  if (kind === 'short_summary') return sermon.value?.short_summary ?? ''
  return ''
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

async function selectSection(section: SermonSection): Promise<void> {
  activeSection.value = section
  await nextTick()
  sectionTabs.value?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'start',
  })
}

async function startPlayback(element: HTMLAudioElement): Promise<void> {
  playbackError.value = false
  playbackErrorDetail.value = ''
  try {
    await playHtmlAudio(element)
  } catch (error) {
    if (isHtmlAudioAbortError(error)) return
    playing.value = false
    if (await recoverRejectedAudio(element)) {
      try {
        await element.play()
      } catch (playError) {
        if (playError instanceof DOMException && playError.name === 'NotAllowedError') return
        if (isHtmlAudioAbortError(playError)) return
        markPlaybackError(element)
      }
      return
    }
    markPlaybackError(element)
  }
}

function markPlaybackError(element = audio.value): void {
  playbackError.value = true
  playbackErrorDetail.value = element ? describeHtmlAudioError(element) : ''
}

function releaseAudioBlobFallback(): void {
  audioFallbackGeneration += 1
  audioFallbackPromise = undefined
  preparingAudioFallback.value = false
  if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
  audioBlobUrl = ''
}

async function recoverRejectedAudio(element = audio.value): Promise<boolean> {
  if (!element) return false
  if (element.src.startsWith('blob:')) return false
  if (
    element.error?.code !== 4 ||
    element.readyState !== HTMLMediaElement.HAVE_NOTHING ||
    element.networkState !== HTMLMediaElement.NETWORK_NO_SOURCE
  ) {
    return false
  }
  if (audioFallbackPromise) return audioFallbackPromise

  const sourceUrl = activeAudioUrl.value
  if (!sourceUrl) return false
  const generation = ++audioFallbackGeneration
  preparingAudioFallback.value = true
  playbackError.value = false
  playbackErrorDetail.value = ''

  const pending = (async () => {
    try {
      const objectUrl = await prepareHtmlAudioBlobFallback(element, sourceUrl)
      if (
        generation !== audioFallbackGeneration ||
        sourceUrl !== activeAudioUrl.value ||
        element !== audio.value
      ) {
        URL.revokeObjectURL(objectUrl)
        return false
      }
      if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
      audioBlobUrl = objectUrl
      playbackError.value = false
      playbackErrorDetail.value = ''
      return true
    } catch {
      if (generation === audioFallbackGeneration) markPlaybackError(element)
      return false
    } finally {
      if (generation === audioFallbackGeneration) {
        preparingAudioFallback.value = false
        audioFallbackPromise = undefined
      }
    }
  })()
  audioFallbackPromise = pending
  return pending
}

function handleAudioError(): void {
  const element = audio.value
  if (!element || element.src.startsWith('blob:')) {
    markPlaybackError(element)
    return
  }
  void recoverRejectedAudio(element).then((recovered) => {
    if (!recovered && !playbackError.value) markPlaybackError(element)
  })
}

async function togglePlayback(): Promise<void> {
  const element = audio.value
  if (!element) return
  if (playing.value) {
    element.pause()
    return
  }
  await startPlayback(element)
}

async function setAudioVariant(variant: AudioVariant): Promise<void> {
  if (audioVariant.value === variant) return
  const element = audio.value
  const wasPlaying = playing.value
  const position = element?.currentTime ?? currentSeconds.value
  releaseAudioBlobFallback()
  audioVariant.value = variant
  playbackError.value = false
  playbackErrorDetail.value = ''
  audioReloadToken.value += 1
  await nextTick()
  const next = audio.value
  if (!next) return
  const restorePosition = () => {
    next.currentTime = position
    currentSeconds.value = position
  }
  next.addEventListener('loadedmetadata', restorePosition, { once: true })
  if (!wasPlaying) return
  await startPlayback(next)
}

async function seekTo(seconds: number): Promise<void> {
  const element = audio.value
  if (!element) return
  element.currentTime = seconds
  currentSeconds.value = seconds
  await startPlayback(element)
}

async function refreshPrivateAudioLink(): Promise<void> {
  const id = String(route.params.id)
  if (!id || refreshingAudio.value || !sermon.value) return
  const position = audio.value?.currentTime ?? currentSeconds.value
  refreshingAudio.value = true
  releaseAudioBlobFallback()
  playbackError.value = false
  playbackErrorDetail.value = ''
  audio.value?.pause()
  playing.value = false
  try {
    const links = await loadSermonAudioLinks(id)
    if (String(route.params.id) !== id || !sermon.value) return
    sermon.value = {
      ...sermon.value,
      ...links,
    }
    audioReloadToken.value += 1
    await nextTick()
    const element = audio.value
    if (!element) return
    await waitForHtmlAudioCanPlay(element)
    element.currentTime = position
    currentSeconds.value = position
    try {
      await element.play()
    } catch (error) {
      if (isHtmlAudioAbortError(error)) return
      if (error instanceof DOMException && error.name === 'NotAllowedError') return
      throw error
    }
  } catch {
    markPlaybackError()
  } finally {
    refreshingAudio.value = false
  }
}

function seekFromPointerEvent(event: PointerEvent): void {
  if (!audio.value || !sermon.value) return
  const track = event.currentTarget
  if (!(track instanceof HTMLElement)) return
  const seconds =
    seekRatioFromClientX(track, event.clientX) * sermon.value.duration_seconds
  audio.value.currentTime = seconds
  currentSeconds.value = seconds
}

function beginTrackScrub(event: PointerEvent): void {
  if (!audio.value || !sermon.value) return
  const track = event.currentTarget
  if (!(track instanceof HTMLElement)) return
  scrubbing.value = true
  playbackError.value = false
  track.setPointerCapture(event.pointerId)
  seekFromPointerEvent(event)
}

function moveTrackScrub(event: PointerEvent): void {
  if (!scrubbing.value) return
  seekFromPointerEvent(event)
}

async function endTrackScrub(event: PointerEvent): Promise<void> {
  if (!scrubbing.value) return
  scrubbing.value = false
  const track = event.currentTarget
  if (track instanceof HTMLElement && track.hasPointerCapture(event.pointerId)) {
    track.releasePointerCapture(event.pointerId)
  }
  seekFromPointerEvent(event)
  if (!audio.value) return
  await startPlayback(audio.value)
}

function closeActionsModal(): void {
  if (regenerating.value || regeneratingMagisterium.value || deleting.value) return
  shareMessage.value = ''
  deleteMessage.value = ''
  contextMessage.value = ''
  actionsView.value = null
}

function openRegenerateAction(): void {
  if (actionsView.value === 'regenerate') {
    closeActionsModal()
    return
  }
  regenerateMessage.value = ''
  const current = sermon.value
  regenerateStartClock.value = formatClock(current?.consider_start_seconds ?? 0)
  regenerateEndClock.value = formatClock(
    current?.consider_end_seconds ?? current?.duration_seconds ?? 0,
  )
  regenerateAudioSource.value =
    current?.has_isolated_audio && current.transcription_audio_source === 'isolated'
      ? 'isolated'
      : 'original'
  actionsView.value = 'regenerate'
}

function resolveRegenerateWindow():
  | {
      consider_start_seconds: number | null
      consider_end_seconds: number | null
      transcription_audio_source?: 'isolated' | 'original'
    }
  | null {
  if (!sermon.value) return null
  const duration = sermon.value.duration_seconds
  const start = parseClock(regenerateStartClock.value)
  const end = parseClock(regenerateEndClock.value)
  if (start === null || end === null) {
    regenerateMessage.value = 'Use mm:ss (or h:mm:ss) for the start and end times.'
    return null
  }
  if (start >= duration) {
    regenerateMessage.value = 'Start time must be before the end of the recording.'
    return null
  }
  if (end <= start) {
    regenerateMessage.value = 'End time must be after the start time.'
    return null
  }
  if (end > duration) {
    regenerateMessage.value = 'End time cannot be after the end of the recording.'
    return null
  }
  return {
    consider_start_seconds: start <= 0 ? null : start,
    consider_end_seconds: end >= duration ? null : end,
    ...(sermon.value.has_isolated_audio
      ? { transcription_audio_source: regenerateAudioSource.value }
      : {}),
  }
}

function magisteriumStatusStamp(status: Pick<
  ServerSermonStatus,
  'related_sources_updated_at' | 'doctrinal_review_updated_at'
>): string {
  return [
    `related_sources:${status.related_sources_updated_at ?? ''}`,
    `doctrinal_review:${status.doctrinal_review_updated_at ?? ''}`,
  ].join('|')
}

function magisteriumArtifactStamp(detail: ServerSermonDetail): string {
  const related = detail.study_artifacts.find((item) => item.kind === 'related_sources')
  const doctrinal = detail.study_artifacts.find((item) => item.kind === 'doctrinal_review')
  return magisteriumStatusStamp({
    related_sources_updated_at: related?.updated_at ?? null,
    doctrinal_review_updated_at: doctrinal?.updated_at ?? null,
  })
}

function clearMagisteriumPoll(): void {
  if (magisteriumPollTimer !== undefined) {
    clearTimeout(magisteriumPollTimer)
    magisteriumPollTimer = undefined
  }
}

async function pollMagisteriumRegeneration(
  id: string,
  beforeStamp: string,
  attempt = 0,
): Promise<void> {
  if (String(route.params.id) !== id) return
  try {
    const status = await loadSermonStatus(id)
    if (String(route.params.id) !== id) return
    if (
      status.processing_status === 'ready' &&
      magisteriumStatusStamp(status) !== beforeStamp
    ) {
      if (sermon.value) {
        const artifacts = await loadStudyArtifacts(id)
        if (String(route.params.id) !== id || !sermon.value) return
        sermon.value = { ...sermon.value, study_artifacts: artifacts }
      }
      regeneratingMagisterium.value = false
      regenerateMessage.value = 'Related sources and Doctrinal review were refreshed.'
      return
    }
  } catch {
    // Keep polling; worker may still be running.
  }
  if (attempt >= 45) {
    regeneratingMagisterium.value = false
    regenerateMessage.value =
      'Magisterium AI is still running. Reopen this Sermon in a minute to see updates.'
    return
  }
  magisteriumPollTimer = setTimeout(() => {
    void pollMagisteriumRegeneration(id, beforeStamp, attempt + 1)
  }, 2000)
}

async function regenerateCurrentSermon(): Promise<void> {
  if (!sermon.value || regenerating.value || regeneratingMagisterium.value) return
  const window = resolveRegenerateWindow()
  if (!window) return
  regenerating.value = true
  regenerateMessage.value = ''
  try {
    audio.value?.pause()
    const current = sermon.value
    const queued = await regenerateSermon(current.id, window)
    actionsView.value = null
    applyLoadedSermon(
      {
        ...current,
        ...queued,
      },
      queued.id,
    )
  } catch (error) {
    regenerateMessage.value =
      error instanceof Error ? error.message : 'This Sermon could not be regenerated.'
  } finally {
    regenerating.value = false
  }
}

async function regenerateMagisteriumOnly(): Promise<void> {
  if (!sermon.value || regenerating.value || regeneratingMagisterium.value) return
  const current = sermon.value
  regeneratingMagisterium.value = true
  regenerateMessage.value = ''
  clearMagisteriumPoll()
  try {
    const beforeStamp = magisteriumArtifactStamp(current)
    await regenerateMagisteriumSermon(current.id)
    actionsView.value = null
    regenerateMessage.value = 'Refreshing Related sources and Doctrinal review…'
    await pollMagisteriumRegeneration(current.id, beforeStamp)
  } catch (error) {
    regeneratingMagisterium.value = false
    regenerateMessage.value =
      error instanceof Error
        ? error.message
        : 'Magisterium AI notes could not be regenerated.'
  }
}

async function openShareAction(): Promise<void> {
  if (actionsView.value === 'share') {
    closeActionsModal()
    return
  }
  actionsView.value = 'share'
  shareMessage.value = ''
  if (!sermon.value) return
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

async function openDetailsAction(): Promise<void> {
  if (actionsView.value === 'details') {
    closeActionsModal()
    return
  }
  actionsView.value = 'details'
  contextMessage.value = ''
  churchSuggestions.value = []
  if (!sermon.value) return
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

function openDeleteAction(): void {
  if (actionsView.value === 'delete') {
    closeActionsModal()
    return
  }
  deleteMessage.value = ''
  actionsView.value = 'delete'
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
  const place = sermon.value ? recordingCapturePlace(sermon.value) : null
  if (!place) {
    contextMessage.value =
      'Nearby Churches need the place captured with this recording. Older Sermons may not have one — add a Church manually.'
    churchSuggestions.value = []
    return
  }

  findingChurches.value = true
  churchSuggestions.value = []
  contextMessage.value = ''
  try {
    churchSuggestions.value = await loadNearbyChurches(place.latitude, place.longitude)
    contextMessage.value = churchSuggestions.value.length
      ? 'Choose a Church near where this was recorded to add it to your private place book.'
      : 'No Churches were found near where this was recorded. You can still add one manually.'
  } catch (error) {
    contextMessage.value =
      error instanceof Error
        ? error.message
        : 'Churches near where this was recorded could not be suggested.'
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
    actionsView.value = null
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

async function hydrateStudyArtifacts(id: string): Promise<void> {
  if (!sermon.value || sermon.value.id !== id) return
  loadingArtifacts.value = true
  try {
    const artifacts = await loadStudyArtifacts(id)
    if (!sermon.value || sermon.value.id !== id) return
    sermon.value = { ...sermon.value, study_artifacts: artifacts }
  } catch (error) {
    if (!sermon.value || sermon.value.id !== id) return
    editMessage.value =
      error instanceof Error ? error.message : 'Study notes could not be loaded.'
  } finally {
    if (sermon.value?.id === id) loadingArtifacts.value = false
  }
}

async function ensureRawTranscriptLoaded(): Promise<void> {
  const current = sermon.value
  if (!current?.transcript) return
  if (current.transcript.raw_segments) return
  if (loadingRawTranscript.value) return
  loadingRawTranscript.value = true
  try {
    const transcript = await loadTranscript(current.id, { includeRaw: true })
    if (!sermon.value || sermon.value.id !== current.id) return
    sermon.value = {
      ...sermon.value,
      transcript: {
        ...sermon.value.transcript!,
        ...transcript,
      },
    }
  } catch (error) {
    if (!sermon.value || sermon.value.id !== current.id) return
    transcriptMessage.value =
      error instanceof Error ? error.message : 'Unredacted Transcript could not be loaded.'
  } finally {
    loadingRawTranscript.value = false
  }
}

async function setTranscriptLayout(layout: TranscriptLayout): Promise<void> {
  transcriptLayout.value = layout
  if (layout === 'raw') await ensureRawTranscriptLoaded()
}

function applyLoadedSermon(loadedSermon: ServerSermonDetail, id: string): void {
  clearProcessingPoll()
  errorMessage.value = ''
  failedSermonId.value = ''

  if (loadedSermon.processing_status === 'ready') {
    processingSermon.value = undefined
    sermon.value = loadedSermon
    audioVariant.value = loadedSermon.has_playback_audio ? 'playback' : 'original'
    reflectionContent.value = loadedSermon.reflections[0]?.content ?? ''
    void hydrateStudyArtifacts(id)
    if (transcriptLayout.value === 'raw') void ensureRawTranscriptLoaded()
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
    const status = await loadSermonStatus(id)
    if (String(route.params.id) !== id) return
    if (status.processing_status === 'ready') {
      const loadedSermon = await loadServerSermon(id)
      if (String(route.params.id) === id) applyLoadedSermon(loadedSermon, id)
      return
    }
    if (processingSermon.value) {
      processingSermon.value = {
        ...processingSermon.value,
        processing_status: status.processing_status,
        processing_message: status.processing_message,
        updated_at: status.updated_at,
      }
    }
    if (status.processing_status === 'failed') {
      failedSermonId.value = status.id
      clearProcessingPoll()
    } else {
      scheduleProcessingPoll(id)
    }
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
  clearMagisteriumPoll()
  releaseAudioBlobFallback()
  loading.value = true
  loadingArtifacts.value = false
  loadingRawTranscript.value = false
  errorMessage.value = ''
  failedSermonId.value = ''
  sermon.value = undefined
  processingSermon.value = undefined
  playing.value = false
  currentSeconds.value = 0
  playbackError.value = false
  playbackErrorDetail.value = ''
  refreshingAudio.value = false
  audioReloadToken.value += 1
  audioVariant.value = 'playback'
  regeneratingMagisterium.value = false
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
  actionsView.value = null
  shareLink.value = null
  shareMessage.value = ''
  deleteMessage.value = ''
  regenerateMessage.value = ''
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

function setActionsBackgroundInert(inert: boolean): void {
  for (const selector of [
    '.app-header',
    '.app-content',
    '.record-control',
    '.audio-player--docked',
  ]) {
    const element = document.querySelector<HTMLElement>(selector)
    element?.toggleAttribute('inert', inert)
    if (inert) element?.setAttribute('aria-hidden', 'true')
    else element?.removeAttribute('aria-hidden')
  }
}

function onActionsModalKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeActionsModal()
  }
}

watch(actionsView, async (view) => {
  const open = view !== null
  document.body.classList.toggle('sermon-actions-lock', open)
  setActionsBackgroundInert(open)
  if (open) {
    window.addEventListener('keydown', onActionsModalKeydown)
    await nextTick()
    actionsPanel.value?.focus()
    return
  }
  window.removeEventListener('keydown', onActionsModalKeydown)
})

watch(
  () => Boolean(sermon.value),
  (docked) => {
    document.body.classList.toggle('sermon-player-dock', docked)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  releaseAudioBlobFallback()
  clearProcessingPoll()
  clearMagisteriumPoll()
  window.removeEventListener('keydown', onActionsModalKeydown)
  document.body.classList.remove('sermon-actions-lock')
  document.body.classList.remove('sermon-player-dock')
  setActionsBackgroundInert(false)
})
</script>

<template>
  <main class="sermon-detail page-gather" :class="{ 'sermon-detail--docked': sermon }">
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
        <div class="sermon-header__tags" aria-label="Tags">
          <div v-if="editingTags" class="tag-editor tag-editor--header">
            <div class="tag-editor__list">
              <span v-for="(tag, index) in tagEdits" :key="`${tag}-${index}`" class="tag-chip">
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
          <template v-else>
            <div class="tag-list tag-list--header">
              <RouterLink
                v-for="tag in sermon.tag_suggestions"
                :key="tag"
                class="tag-chip"
                :to="{ path: '/', query: { tag } }"
                :aria-label="`Show Sermons tagged ${tag}`"
              >
                {{ tag }}
              </RouterLink>
              <p v-if="!sermon.tag_suggestions.length" class="tag-list__empty tag-list__empty--header">
                No Tags yet
              </p>
              <button
                class="sermon-header__tag-edit"
                type="button"
                aria-label="Edit Tags"
                @click="beginTagEdit"
              >
                <PencilLine :size="15" aria-hidden="true" />
              </button>
            </div>
          </template>
          <p v-if="tagMessage" class="artifact__message" role="status">
            {{ tagMessage }}
          </p>
        </div>
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
              <strong
                :class="{
                  'is-unset': !sermon.occasion_kind && !sermon.liturgical_day,
                }"
              >
                {{
                  occasionLabel(sermon.occasion_kind) ||
                  sermon.liturgical_day ||
                  'Not specified'
                }}
              </strong>
              <small v-if="sermon.occasion_kind && sermon.liturgical_day">{{
                sermon.liturgical_day
              }}</small>
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
          <button
            type="button"
            :aria-expanded="actionsView === 'details'"
            aria-controls="sermon-actions-dialog"
            @click="openDetailsAction"
          >
            <PencilLine :size="16" aria-hidden="true" />
            Edit details
          </button>
          <button
            type="button"
            :aria-expanded="actionsView === 'share'"
            aria-controls="sermon-actions-dialog"
            @click="openShareAction"
          >
            <Share2 :size="16" aria-hidden="true" />
            Share Sermon
          </button>
          <button type="button" @click="router.push(`/sermons/${sermon.id}/email`)">
            <Mail :size="16" aria-hidden="true" />
            Email handout
          </button>
          <button
            class="sermon-header__regenerate"
            type="button"
            :aria-expanded="actionsView === 'regenerate'"
            aria-controls="sermon-actions-dialog"
            :disabled="regenerating || regeneratingMagisterium"
            @click="openRegenerateAction"
          >
            <RotateCcw
              :size="16"
              :class="{ 'is-spinning': regeneratingMagisterium }"
              aria-hidden="true"
            />
            {{ regeneratingMagisterium ? 'Refreshing Magisterium…' : 'Regenerate' }}
          </button>
          <button
            class="sermon-header__delete"
            type="button"
            :aria-expanded="actionsView === 'delete'"
            aria-controls="sermon-actions-dialog"
            :disabled="deleting"
            @click="openDeleteAction"
          >
            <Trash2 :size="16" aria-hidden="true" />
            Delete Sermon
          </button>
        </div>
      </header>

      <p
        v-if="actionsView !== 'regenerate' && regenerateMessage"
        class="sermon-regenerate-status"
        role="status"
      >
        {{ regenerateMessage }}
      </p>

      <Teleport to="body">
        <div
          v-if="actionsView && sermon"
          class="sermon-actions"
          role="presentation"
          @click.self="closeActionsModal"
        >
          <div
            id="sermon-actions-dialog"
            ref="actionsPanel"
            class="sermon-actions__panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sermon-actions-title"
            tabindex="-1"
          >
            <header class="sermon-actions__header">
              <div class="sermon-actions__heading">
                <p class="rubric-label">{{ actionsModalRubric }}</p>
                <h2 id="sermon-actions-title">{{ actionsModalTitle }}</h2>
              </div>
              <button
                type="button"
                class="sermon-actions__close"
                :disabled="regenerating || regeneratingMagisterium || deleting"
                aria-label="Close"
                @click="closeActionsModal"
              >
                <X :size="18" :stroke-width="1.8" aria-hidden="true" />
              </button>
            </header>

            <div class="sermon-actions__body">
              <section v-if="actionsView === 'details'" class="context-panel context-panel--modal" aria-label="Sermon details">
                <p class="sermon-actions__lead">
                  New Sermons begin with an AI-suggested title. Change it whenever you like, and reuse
                  Churches and Preachers from your private books.
                </p>
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
                    <div class="context-field__actions">
                      <button
                        class="context-field__locate"
                        type="button"
                        :disabled="findingChurches || contextSaving"
                        @click="suggestNearbyChurches"
                      >
                        <LocateFixed :size="15" aria-hidden="true" />
                        {{
                          findingChurches
                            ? 'Finding near recording…'
                            : 'Find Churches near recording'
                        }}
                      </button>
                      <button type="button" @click="addingChurch = !addingChurch">
                        {{ addingChurch ? 'Cancel new Church' : 'Add a Church' }}
                      </button>
                    </div>
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

              <section v-else-if="actionsView === 'share'" class="share-panel share-panel--modal" aria-label="Share this Sermon">
                <p class="sermon-actions__lead">
                  Anyone with the link can read the Study artifacts and Transcript and listen to the
                  recording. Your private Reflection is always excluded.
                </p>
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

              <section
                v-else-if="actionsView === 'regenerate'"
                class="sermon-regenerate-confirm sermon-regenerate-confirm--modal"
                aria-label="Regenerate this Sermon"
              >
                <p class="sermon-actions__lead">
                  Full regeneration rewrites the Transcript, title suggestion, Study artifacts, Scripture
                  references, Tags, and Related Sermons from the selected recording. Your existing
                  summaries and other AI-generated notes will be permanently replaced.
                </p>
                <p class="sermon-actions__lead">
                  Magisterium AI only refreshes Related sources and Doctrinal review from the current
                  Transcript — everything else stays put. Reflections and Share links are kept either way.
                  The audio itself is never deleted or trimmed.
                </p>
                <div
                  v-if="sermon.has_isolated_audio"
                  class="sermon-regenerate-source"
                >
                  <p class="rubric-label">Audio to transcribe</p>
                  <p>
                    Transcripts use the original recording by default. Isolation still runs in the
                    background — choose Isolated Speaker Voice only if ambient noise is drowning out the speech.
                  </p>
                  <div class="sermon-regenerate-source__choices" role="group" aria-label="Audio to transcribe">
                    <button
                      type="button"
                      :aria-pressed="regenerateAudioSource === 'original'"
                      :class="{ 'is-active': regenerateAudioSource === 'original' }"
                      :disabled="regenerating || regeneratingMagisterium"
                      @click="regenerateAudioSource = 'original'"
                    >
                      Original
                    </button>
                    <button
                      type="button"
                      :aria-pressed="regenerateAudioSource === 'isolated'"
                      :class="{ 'is-active': regenerateAudioSource === 'isolated' }"
                      :disabled="regenerating || regeneratingMagisterium"
                      @click="regenerateAudioSource = 'isolated'"
                    >
                      Isolated Speaker Voice
                    </button>
                  </div>
                </div>
                <div class="sermon-regenerate-window">
                  <p class="rubric-label">Audio window to consider</p>
                  <p>
                    Optionally skip prelude or trailing silence. Only speech inside this window feeds
                    the new Transcript and Study notes.
                  </p>
                  <div class="sermon-regenerate-window__fields">
                    <label>
                      Start
                      <input
                        v-model="regenerateStartClock"
                        type="text"
                        inputmode="numeric"
                        autocomplete="off"
                        :disabled="regenerating || regeneratingMagisterium"
                        aria-label="Regenerate start time"
                        placeholder="00:00"
                      />
                    </label>
                    <label>
                      End
                      <input
                        v-model="regenerateEndClock"
                        type="text"
                        inputmode="numeric"
                        autocomplete="off"
                        :disabled="regenerating || regeneratingMagisterium"
                        aria-label="Regenerate end time"
                        :placeholder="formatClock(sermon.duration_seconds)"
                      />
                    </label>
                  </div>
                </div>
                <p v-if="regenerateMessage" class="sermon-delete-confirm__error" role="alert">
                  {{ regenerateMessage }}
                </p>
                <div class="sermon-delete-confirm__actions sermon-regenerate-confirm__actions">
                  <button
                    type="button"
                    :disabled="regenerating || regeneratingMagisterium"
                    @click="closeActionsModal"
                  >
                    Keep current notes
                  </button>
                  <button
                    type="button"
                    :disabled="regenerating || regeneratingMagisterium"
                    @click="regenerateMagisteriumOnly"
                  >
                    {{
                      regeneratingMagisterium
                        ? 'Starting Magisterium…'
                        : 'Regenerate Magisterium AI only'
                    }}
                  </button>
                  <button
                    class="sermon-delete-confirm__delete"
                    type="button"
                    :disabled="regenerating || regeneratingMagisterium"
                    @click="regenerateCurrentSermon"
                  >
                    {{ regenerating ? 'Starting…' : 'Regenerate and replace notes' }}
                  </button>
                </div>
              </section>

              <section
                v-else-if="actionsView === 'delete'"
                class="sermon-delete-confirm sermon-delete-confirm--modal"
                aria-label="Delete this Sermon"
              >
                <p class="sermon-actions__lead">
                  This removes the recording, Transcript, Study artifacts, Reflections, and any active
                  Share link. It cannot be undone.
                </p>
                <p v-if="deleteMessage" class="sermon-delete-confirm__error" role="alert">
                  {{ deleteMessage }}
                </p>
                <div class="sermon-delete-confirm__actions">
                  <button type="button" :disabled="deleting" @click="closeActionsModal">
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
            </div>
          </div>
        </div>
      </Teleport>

      <SermonSectionTabs
        ref="sectionTabs"
        :active-section="activeSection"
        include-reflection
        @select="selectSection"
      />

      <p v-if="editMessage" class="edit-message" role="status">{{ editMessage }}</p>

      <div
        :id="`sermon-panel-${activeSection}`"
        class="sermon-content"
        role="tabpanel"
        :aria-labelledby="`sermon-tab-${activeSection}`"
      >
        <template v-if="activeSection === 'study'">
          <section class="artifact artifact--summary">
            <div class="summary-brief">
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
            </div>

            <div class="summary-long">
              <div class="summary-long__toolbar">
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
              <div v-else class="artifact__prose artifact__prose--compact">
                <p v-for="paragraph in paragraphs(artifact('long_summary'))" :key="paragraph">
                  {{ paragraph }}
                </p>
              </div>
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
              <p class="artifact-editor__hint">
                Keep one numbered line per point. Optional timestamps like
                <code>1. [05:12] Point text</code> stay seekable.
              </p>
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
              <li v-for="(point, index) in outlinePoints" :key="`${index}-${point.text}`">
                <button
                  v-if="point.start_seconds != null"
                  type="button"
                  class="outline__seek"
                  :aria-label="`Play from ${timestamp(point.start_seconds)}`"
                  @click="seekTo(point.start_seconds)"
                >
                  {{ timestamp(point.start_seconds) }}
                </button>
                <span v-else class="outline__seek outline__seek--empty" aria-hidden="true"></span>
                <span>{{ point.text }}</span>
              </li>
            </ol>
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
              <p class="artifact-editor__hint">
                Keep one quotation per line, using the Transcript's words in order.
              </p>
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

          <section
            v-if="artifact('call_to_action') || artifact('practical_next_steps')"
            class="artifact artifact--call"
          >
            <div class="artifact__heading">
              <h2>Action Items</h2>
              <button
                v-if="artifact('call_to_action')"
                class="artifact__edit"
                type="button"
                aria-label="Edit action item"
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
                aria-label="Action item"
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
            <p v-else-if="artifact('call_to_action')" class="artifact__call">
              {{ artifact('call_to_action') }}
            </p>

            <div v-if="artifact('practical_next_steps')" class="action-items__carry">
              <div class="action-items__carry-heading">
                <p class="action-items__carry-label">Carry this with you</p>
                <button
                  class="artifact__edit"
                  type="button"
                  aria-label="Edit carry-this-with-you steps"
                  @click="beginArtifactEdit('practical_next_steps')"
                >
                  <PencilLine :size="16" />
                </button>
              </div>
              <div v-if="editingKind === 'practical_next_steps'" class="artifact-editor">
                <textarea
                  v-model="editContent"
                  rows="8"
                  aria-label="Carry this with you"
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
            </div>
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

          <section
            v-if="artifact('related_sources')"
            class="artifact artifact--related-sources"
          >
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">For further study</p>
                <h2>Related sources</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit Related sources"
                @click="beginArtifactEdit('related_sources')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <p class="feedback-note">
              Sources suggested via Magisterium AI Search. Confirm relevance before relying on them.
            </p>
            <div v-if="editingKind === 'related_sources'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="12"
                aria-label="Related sources"
              ></textarea>
              <p class="artifact-editor__hint">
                Keep valid JSON with a top-level <code>sources</code> array.
              </p>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <RelatedSourcesList
              v-else-if="relatedSources.length"
              :sources="relatedSources"
            />
            <p v-else class="scripture-links__empty">No related sources were suggested.</p>
          </section>
        </template>

        <template v-else-if="activeSection === 'feedback'">
          <section v-if="artifact('sermon_feedback')" class="artifact artifact--feedback">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">If this sermon were revised</p>
                <h2>Craft feedback</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit craft feedback"
                @click="beginArtifactEdit('sermon_feedback')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <p class="feedback-note">
              Suggestions for conveying the message more clearly — structure, missing points,
              tangents, and application. Not a doctrinal audit.
            </p>
            <div v-if="editingKind === 'sermon_feedback'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="10"
                aria-label="Craft feedback"
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
            <ol v-else class="feedback-list">
              <li v-for="item in numberedItems(artifact('sermon_feedback'))" :key="item">
                {{ item }}
              </li>
            </ol>
          </section>

          <section
            v-if="artifact('doctrinal_review')"
            class="artifact artifact--doctrinal"
          >
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Catholic teaching check</p>
                <h2>Doctrinal review</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit Doctrinal review"
                @click="beginArtifactEdit('doctrinal_review')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <p class="feedback-note">
              Advisory only. Verify every judgment against Scripture and the Church’s Magisterium.
              Generated citations can miss context.
            </p>
            <div v-if="editingKind === 'doctrinal_review'" class="artifact-editor">
              <textarea
                v-model="editContent"
                rows="14"
                aria-label="Doctrinal review"
              ></textarea>
              <p class="artifact-editor__hint">
                Keep valid JSON with <code>findings</code> and optional <code>summary</code>.
              </p>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <DoctrinalFindingsList
              v-else
              :findings="doctrinalReview.findings"
              :empty-summary="doctrinalReview.summary"
            />
          </section>

          <p
            v-if="!artifact('sermon_feedback') && !artifact('doctrinal_review')"
            class="empty-panel"
          >
            Feedback is not available for this sermon yet.
          </p>
        </template>

        <template v-else-if="activeSection === 'hymn'">
          <section v-if="artifact('hymn')" class="artifact hymn-sheet">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Inspired by this sermon</p>
                <h2>{{ hymn.title || 'Hymn' }}</h2>
                <p v-if="hymn.meter" class="hymn-sheet__meter">Meter · {{ hymn.meter }}</p>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit Hymn"
                @click="beginArtifactEdit('hymn')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'hymn'" class="artifact-editor">
              <textarea v-model="editContent" rows="18" aria-label="Hymn"></textarea>
              <p class="artifact-editor__hint">
                Keep the Title and Meter lines, then number each verse on its own block.
              </p>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <div v-else class="hymn-verses">
              <div v-for="(verse, index) in hymn.verses" :key="index" class="hymn-verse">
                <span aria-hidden="true">{{ index + 1 }}</span>
                <p>
                  <template v-for="(line, lineIndex) in verse" :key="lineIndex">
                    {{ line }}<br v-if="lineIndex < verse.length - 1" />
                  </template>
                </p>
              </div>
            </div>
          </section>
          <section
            v-if="artifact('hymn_tune_suggestions')"
            class="artifact tune-suggestions"
          >
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Sing it with</p>
                <h2>Compatible tunes</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit Hymn tune suggestions"
                @click="beginArtifactEdit('hymn_tune_suggestions')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div
              v-if="editingKind === 'hymn_tune_suggestions'"
              class="artifact-editor"
            >
              <textarea
                v-model="editContent"
                rows="7"
                aria-label="Hymn tune suggestions"
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
            <ul v-else class="tune-list">
              <li v-for="tune in hymnTunes" :key="tune.name">
                <strong>{{ tune.name }}</strong>
                <span>{{ tune.traditions }}</span>
              </li>
            </ul>
          </section>
          <section
            v-if="!artifact('hymn') && !artifact('hymn_tune_suggestions')"
            class="artifact artifact--empty"
          >
            <p class="rubric-label">Earlier sermon</p>
            <h2>No hymn was generated</h2>
            <p>Hymns are included when newly uploaded Sermons are prepared.</p>
          </section>
        </template>

        <template v-else-if="activeSection === 'transcript'">
          <section class="artifact transcript">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">{{ transcriptViewMeta.rubric }}</p>
                <h2>Follow the sermon</h2>
              </div>
              <button
                v-if="originalTranscriptSegments.length && transcriptLayout !== 'raw'"
                class="artifact__edit"
                type="button"
                aria-label="Edit Transcript"
                @click="beginTranscriptEdit"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div class="transcript-controls">
              <div class="transcript-view-toggle" role="group" aria-label="Transcript layout">
                <button
                  type="button"
                  :class="{ active: transcriptLayout === 'timeline' }"
                  :aria-pressed="transcriptLayout === 'timeline'"
                  @click="void setTranscriptLayout('timeline')"
                >
                  Timeline
                </button>
                <button
                  type="button"
                  :class="{ active: transcriptLayout === 'reading' }"
                  :aria-pressed="transcriptLayout === 'reading'"
                  @click="void setTranscriptLayout('reading')"
                >
                  Reading
                </button>
                <button
                  type="button"
                  :class="{ active: transcriptLayout === 'raw' }"
                  :aria-pressed="transcriptLayout === 'raw'"
                  @click="void setTranscriptLayout('raw')"
                >
                  Full tape
                </button>
              </div>
              <div
                v-if="transcriptLayout !== 'raw'"
                class="transcript-edition"
                role="group"
                aria-label="Transcript wording"
              >
                <span class="transcript-edition__label">Wording</span>
                <div class="transcript-edition__toggle">
                  <button
                    type="button"
                    :class="{ active: transcriptEdition === 'polished' }"
                    :aria-pressed="transcriptEdition === 'polished'"
                    @click="transcriptEdition = 'polished'"
                  >
                    Polished
                  </button>
                  <button
                    type="button"
                    :class="{ active: transcriptEdition === 'original' }"
                    :aria-pressed="transcriptEdition === 'original'"
                    @click="transcriptEdition = 'original'"
                  >
                    As spoken
                  </button>
                </div>
              </div>
            </div>
            <p class="transcript__note">{{ transcriptViewMeta.note }}</p>
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
            <div v-else-if="transcriptLayout === 'timeline'" class="transcript__segments">
              <div
                v-for="segment in usingPolishedTranscript
                  ? displayTranscriptSegments
                  : originalTranscriptSegments"
                :key="`${transcriptEdition}-${segment.start_seconds}-${segment.text}`"
                class="transcript__segment transcript__segment--virtual"
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
            <div v-else-if="transcriptLayout === 'raw'" class="transcript__segments">
              <p v-if="loadingRawTranscript" class="transcript__empty">Loading diarization…</p>
              <div
                v-for="segment in rawTranscriptSegments"
                :key="`${segment.speaker}-${segment.start_seconds}-${segment.text}`"
                class="transcript__segment transcript__segment--raw transcript__segment--virtual"
              >
                <button
                  type="button"
                  :aria-label="`Play from ${timestamp(segment.start_seconds)}`"
                  @click="seekTo(segment.start_seconds)"
                >
                  {{ timestamp(segment.start_seconds) }}
                </button>
                <div>
                  <span class="transcript__speaker">{{ segment.speaker }}</span>
                  <p>{{ segment.text }}</p>
                </div>
              </div>
              <p v-if="!rawTranscriptSegments.length" class="transcript__empty">
                No unredacted segments are stored for this Sermon yet. Regenerate to capture the
                full diarization.
              </p>
            </div>
            <div v-else class="transcript__reading">
              <p
                v-for="(paragraph, index) in usingPolishedTranscript
                  ? cleanedReadingParagraphs
                  : originalReadingParagraphs"
                :key="index"
              >
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
          <section v-if="artifact('quiz')" class="artifact quiz">
            <div class="artifact__heading">
              <div>
                <p class="rubric-label">Check the takeaways</p>
                <h2>Comprehension quiz</h2>
              </div>
              <button
                class="artifact__edit"
                type="button"
                aria-label="Edit comprehension quiz"
                @click="beginArtifactEdit('quiz')"
              >
                <PencilLine :size="16" />
              </button>
            </div>
            <div v-if="editingKind === 'quiz'" class="artifact-editor">
              <textarea v-model="editContent" rows="16" aria-label="Comprehension quiz"></textarea>
              <p class="artifact-editor__hint">
                Keep each Q line paired with its A line, with a blank line between pairs.
              </p>
              <div class="artifact-editor__actions">
                <button type="button" @click="cancelArtifactEdit">
                  <X :size="15" /> Cancel
                </button>
                <button type="button" :disabled="savingEdit" @click="saveArtifactEdit">
                  <Check :size="15" />{{ savingEdit ? 'Saving…' : 'Save edit' }}
                </button>
              </div>
            </div>
            <ol v-else class="quiz-list">
              <li v-for="item in quiz" :key="item.question">
                <p>{{ item.question }}</p>
                <details>
                  <summary>Reveal answer</summary>
                  <p>{{ item.answer }}</p>
                </details>
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

      <Teleport to="body">
        <section class="audio-player audio-player--docked" aria-label="Sermon audio player">
          <audio
            :key="`${activeAudioUrl}:${audioReloadToken}`"
            ref="audio"
            :src="activeAudioUrl"
            preload="none"
            @play="playing = true"
            @pause="playing = false"
            @ended="playing = false"
            @timeupdate="currentSeconds = scrubbing ? currentSeconds : (audio?.currentTime ?? 0)"
            @error="handleAudioError"
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
          <div class="audio-player__copy">
            <strong>{{ serverSermonTitle(sermon) }}</strong>
            <span v-if="!playbackError">
              <template v-if="preparingAudioFallback">Preparing mobile playback…</template>
              <template v-else>
                {{ playing ? 'Playing' : 'Listen' }} · {{ timestamp(currentSeconds) }} /
                {{ serverSermonDuration(sermon.duration_seconds) }}
              </template>
            </span>
            <div v-else class="audio-player__error" role="alert">
              <span>
                Audio could not be played. Refresh the private link and try again.
                <small v-if="playbackErrorDetail">{{ playbackErrorDetail }}</small>
              </span>
              <button
                type="button"
                class="audio-player__refresh"
                :disabled="refreshingAudio"
                aria-label="Refresh private audio link"
                @click="refreshPrivateAudioLink"
              >
                <RefreshCw
                  :size="14"
                  :class="{ 'is-spinning': refreshingAudio }"
                  aria-hidden="true"
                />
              </button>
            </div>
            <div
              v-if="sermon.has_playback_audio || sermon.has_isolated_audio"
              class="audio-player__variants"
              role="group"
              aria-label="Optional audio version"
            >
              <button
                v-if="sermon.has_playback_audio"
                type="button"
                :aria-pressed="audioVariant === 'playback'"
                :class="{ 'is-active': audioVariant === 'playback' }"
                @click="setAudioVariant('playback')"
              >
                Normalized
              </button>
              <button
                type="button"
                :aria-pressed="audioVariant === 'original'"
                :class="{ 'is-active': audioVariant === 'original' }"
                @click="setAudioVariant('original')"
              >
                Original
              </button>
              <button
                v-if="sermon.has_isolated_audio"
                type="button"
                :aria-pressed="audioVariant === 'isolated'"
                :class="{ 'is-active': audioVariant === 'isolated' }"
                @click="setAudioVariant('isolated')"
              >
                Isolated Speaker Voice
              </button>
            </div>
          </div>
          <div
            class="audio-player__track"
            role="slider"
            tabindex="0"
            aria-label="Sermon playback position"
            aria-valuemin="0"
            :aria-valuemax="sermon.duration_seconds"
            :aria-valuenow="Math.round(currentSeconds)"
            :aria-valuetext="timestamp(currentSeconds)"
            @pointerdown.prevent="beginTrackScrub"
            @pointermove="moveTrackScrub"
            @pointerup="endTrackScrub"
            @pointercancel="endTrackScrub"
            @keydown.home.prevent="seekTo(0)"
            @keydown.end.prevent="seekTo(sermon.duration_seconds)"
            @keydown.arrow-left.prevent="seekTo(Math.max(0, currentSeconds - 5))"
            @keydown.arrow-right.prevent="
              seekTo(Math.min(sermon.duration_seconds, currentSeconds + 5))
            "
          >
            <span :style="{ width: progressPercent }"></span>
          </div>
        </section>
      </Teleport>
    </article>
  </main>
</template>

<style scoped>
.sermon-detail {
  margin: 0 auto;
  max-width: 58rem;
  padding: 2rem clamp(1.25rem, 5vw, 3.5rem) 10rem;
}

.sermon-detail--docked {
  padding-bottom: calc(8.5rem + env(safe-area-inset-bottom));
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
  margin: 0.8rem 0 0;
  max-width: 18ch;
}

.sermon-header__tags {
  margin: 1rem 0 1.35rem;
}

.sermon-header__tag-edit {
  align-items: center;
  align-self: center;
  background: transparent;
  border: 1px solid var(--color-margin);
  box-sizing: border-box;
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  height: 1.7rem;
  justify-content: center;
  line-height: 1;
  padding: 0;
  width: 1.7rem;
}

.tag-list--header {
  align-items: center;
  margin-top: 0;
}

.tag-list__empty--header {
  font-size: 0.85rem;
  margin: 0;
}

.tag-chip {
  align-items: center;
  background: color-mix(in srgb, var(--color-lapis) 8%, var(--color-vellum));
  border: 1px solid color-mix(in srgb, var(--color-lapis) 28%, var(--color-margin));
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.74rem;
  font-weight: 650;
  gap: 0.35rem;
  letter-spacing: 0.02em;
  line-height: 1;
  padding: 0.42rem 0.7rem;
  text-decoration: none;
}

a.tag-chip:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 2px;
}

.tag-editor--header {
  margin-top: 0;
  width: 100%;
}

.sermon-register {
  background: color-mix(in srgb, var(--color-vellum-light) 82%, transparent);
  border-bottom: 1px solid var(--color-rule-gold);
  border-top: 1px solid var(--color-rule-gold);
  display: grid;
  /* Length needs room for icon + spaced "LENGTH"; 0.7fr was clipping the label. */
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) minmax(0, 1.15fr) minmax(0, 1fr) minmax(6.5rem, 0.9fr);
  margin: 2rem 0 0;
}

.sermon-register__entry {
  min-width: 0;
  padding: 1rem clamp(0.7rem, 2vw, 1.15rem);
}

.sermon-register__entry:last-child {
  min-width: 6.5rem;
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
  max-width: 100%;
  text-transform: uppercase;
  white-space: nowrap;
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
  margin-top: 1.15rem;
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

.sermon-header__actions .sermon-header__regenerate {
  margin-left: auto;
}

.sermon-header__actions .is-spinning {
  animation: processing-spin 0.9s linear infinite;
}

.sermon-header__actions .sermon-header__delete {
  border-color: color-mix(in srgb, var(--color-rubric) 55%, transparent);
  color: var(--color-rubric);
}

.sermon-regenerate-status {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  margin: -0.35rem auto 1.25rem;
  max-width: var(--reading-width);
}

.sermon-actions {
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

.sermon-actions__panel {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  box-shadow: 0 22px 60px rgba(28, 36, 48, 0.24);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  margin: auto;
  max-height: min(46rem, calc(100svh - 1.5rem));
  max-width: 40rem;
  outline: none;
  width: min(100%, 40rem);
}

.sermon-actions__header {
  align-items: start;
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  gap: 0.75rem;
  padding: 0.9rem 1rem 0.9rem 1.1rem;
}

.sermon-actions__heading {
  flex: 1;
  min-width: 0;
}

.sermon-actions__heading h2 {
  font-family: var(--font-display);
  font-size: clamp(1.45rem, 4vw, 1.9rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 40;
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin: 0.3rem 0 0;
}

.sermon-actions__close {
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

.sermon-actions__close:disabled {
  cursor: wait;
  opacity: 0.55;
}

.sermon-actions__close:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 2px;
}

.sermon-actions__body {
  overflow: auto;
  overscroll-behavior: contain;
  padding: 1.15rem clamp(1.1rem, 3vw, 1.6rem) 1.5rem;
}

.sermon-actions__lead {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.55;
  margin: 0 0 1rem;
}

.context-panel--modal,
.share-panel--modal,
.sermon-regenerate-confirm--modal,
.sermon-delete-confirm--modal {
  background: transparent;
  border: 0;
  margin: 0;
  padding: 0;
}

.sermon-regenerate-confirm--modal,
.sermon-delete-confirm--modal {
  display: grid;
  gap: 0.25rem;
}

.sermon-regenerate-confirm__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  justify-content: flex-start;
  margin-top: 1.25rem;
}

.sermon-regenerate-confirm__actions button {
  flex: 1 1 auto;
  min-width: min(100%, 11rem);
  white-space: normal;
}

.sermon-regenerate-source,
.sermon-regenerate-window {
  margin-top: 1.1rem;
}

.sermon-regenerate-source > p,
.sermon-regenerate-window > p {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.86rem;
  line-height: 1.45;
  margin: 0.35rem 0 0.85rem;
}

.sermon-regenerate-source__choices {
  display: inline-flex;
  gap: 0.35rem;
}

.sermon-regenerate-source__choices button {
  background: transparent;
  border: 1px solid var(--color-margin);
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  min-height: 2.1rem;
  padding: 0.35rem 0.75rem;
  text-transform: uppercase;
}

.sermon-regenerate-source__choices button.is-active {
  background: var(--color-lapis);
  border-color: var(--color-lapis);
  color: var(--color-vellum-light);
}

.sermon-regenerate-source__choices button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.sermon-regenerate-window__fields {
  display: grid;
  gap: 0.85rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.sermon-regenerate-window__fields label {
  color: var(--color-ink-muted);
  display: grid;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  gap: 0.35rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.sermon-regenerate-window__fields input {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 1rem;
  letter-spacing: 0;
  padding: 0.65rem 0.75rem;
  text-transform: none;
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

.sermon-delete-confirm--modal,
.sermon-regenerate-confirm--modal {
  align-items: stretch;
  background: transparent;
  border: 0;
  display: grid;
  gap: 0.25rem;
  justify-content: stretch;
  margin: 0;
  padding: 0;
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

.context-panel.context-panel--modal {
  background: transparent;
  border: 0;
  margin: 0;
  padding: 0;
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

.context-field__actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.15rem 1.15rem;
  margin-top: 0.15rem;
}

.context-field > button,
.context-field__actions > button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.74rem;
  font-weight: 650;
  min-height: 2.5rem;
  padding: 0.4rem 0;
  text-align: left;
  white-space: nowrap;
}

.context-field__locate {
  align-items: center;
  display: inline-flex;
  gap: 0.35rem;
}

.context-field > button:disabled,
.context-field__actions > button:disabled {
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

.share-panel.share-panel--modal {
  background: transparent;
  border: 0;
  margin: 0;
  padding: 0;
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

.audio-player--docked {
  align-items: center;
  background: color-mix(in srgb, var(--color-ink) 96%, transparent);
  box-shadow: 0 -10px 30px rgba(28, 36, 48, 0.17);
  color: var(--color-vellum);
  display: grid;
  gap: 1rem;
  grid-template-columns: auto minmax(8rem, auto) minmax(5rem, 20rem);
  justify-content: center;
  left: 0;
  padding: 0.85rem 1rem calc(0.85rem + env(safe-area-inset-bottom));
  position: fixed;
  right: 0;
  bottom: 0;
  width: 100%;
  z-index: 35;
}

.audio-player--docked audio {
  display: none;
}

.audio-player__play {
  align-items: center;
  background: var(--color-vellum);
  border: 0;
  border-radius: 50%;
  color: var(--color-rubric);
  cursor: pointer;
  display: flex;
  height: 2.7rem;
  justify-content: center;
  padding-left: 0.15rem;
  width: 2.7rem;
}

.audio-player__copy strong,
.audio-player__copy > span {
  display: block;
  font-family: var(--font-utility);
}

.audio-player__copy strong {
  font-size: 0.78rem;
  font-weight: 650;
}

.audio-player__copy > span {
  color: rgba(241, 238, 228, 0.65);
  font-size: 0.7rem;
  margin-top: 0.15rem;
}

.audio-player__variants {
  display: inline-flex;
  gap: 0.2rem;
  margin-top: 0.45rem;
}

.audio-player__variants button {
  background: transparent;
  border: 1px solid rgba(241, 238, 228, 0.28);
  color: rgba(241, 238, 228, 0.78);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.62rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  min-height: 1.7rem;
  padding: 0.15rem 0.55rem;
  text-transform: uppercase;
}

.audio-player__variants button.is-active {
  background: var(--color-vellum);
  border-color: var(--color-vellum);
  color: var(--color-ink);
}

.audio-player__track {
  background: rgba(241, 238, 228, 0.2);
  cursor: pointer;
  height: 12px;
  padding: 5px 0;
  touch-action: none;
}

.audio-player__track span {
  background: var(--color-rule-gold);
  display: block;
  height: 2px;
  margin: 0;
  position: relative;
  width: 18%;
}

.audio-player__track span::after {
  display: none;
}

.transcript__segment--raw {
  align-items: start;
}

.transcript__speaker {
  color: var(--color-lapis);
  display: inline-block;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  margin-bottom: 0.2rem;
  text-transform: uppercase;
}

.transcript__empty {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.9rem;
  margin: 0.5rem 0 0;
}

.audio-player__error {
  align-items: center;
  color: color-mix(in srgb, #f1eee4 72%, var(--color-rubric));
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.7rem;
  gap: 0.4rem;
  margin-top: 0.2rem;
}

.audio-player__error small {
  display: block;
  opacity: 0.8;
}

.audio-player__refresh {
  align-items: center;
  background: color-mix(in srgb, var(--color-vellum) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-vellum) 28%, transparent);
  border-radius: 999px;
  color: inherit;
  display: inline-flex;
  flex: 0 0 auto;
  justify-content: center;
  min-height: 1.7rem;
  min-width: 1.7rem;
  padding: 0.2rem;
}

.audio-player__refresh:disabled {
  opacity: 0.7;
}

.audio-player__refresh .is-spinning {
  animation: processing-spin 0.9s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .audio-player__refresh .is-spinning {
    animation: none;
  }
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
  padding: 0 0 1.85rem;
}

.artifact + .artifact {
  padding-top: 1.85rem;
}

.artifact__heading {
  align-items: start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.artifact--summary {
  display: grid;
  gap: 0.85rem;
}

.summary-long {
  border-top: 1px solid color-mix(in srgb, var(--color-margin) 70%, transparent);
  padding-top: 0.85rem;
}

.summary-long__toolbar {
  display: flex;
  justify-content: end;
  margin: -0.35rem 0 -0.55rem;
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
  margin: 0.7rem 0 0;
}

.quotation-list {
  display: grid;
  gap: 1rem;
  margin-top: 1.1rem;
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
  padding-top: 2.35rem;
}

.artifact__call {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 2.6vw, 1.45rem);
  font-variation-settings: 'opsz' 32, 'SOFT' 48;
  letter-spacing: -0.02em;
  line-height: 1.35;
  margin: 0.75rem 0 0;
}

.action-items__carry {
  border-top: 1px solid color-mix(in srgb, var(--color-rule-gold) 35%, var(--color-margin));
  margin-top: 1.25rem;
  padding-top: 0.95rem;
}

.action-items__carry-heading {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

.action-items__carry-label {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  margin: 0;
  text-transform: uppercase;
}

.action-items__carry .practical-steps {
  margin-top: 0.75rem;
}

.practical-steps {
  display: grid;
  gap: 0.7rem;
  list-style: none;
  margin: 1.1rem 0 0;
  padding: 0;
}

.practical-steps li {
  border-left: 2px solid var(--color-rule-gold);
  font-family: var(--font-reading);
  font-size: 0.98rem;
  line-height: 1.55;
  padding: 0.2rem 0 0.2rem 0.9rem;
}

.artifact--feedback {
  background: color-mix(in srgb, var(--color-lapis) 5%, var(--color-vellum-light));
  border: 1px solid color-mix(in srgb, var(--color-lapis) 22%, var(--color-margin));
  border-bottom: 1px solid color-mix(in srgb, var(--color-lapis) 22%, var(--color-margin));
  margin-top: 3.5rem;
  padding: clamp(1.25rem, 4vw, 1.85rem);
}

.artifact + .artifact--feedback {
  padding-top: clamp(1.25rem, 4vw, 1.85rem);
}

.feedback-list {
  list-style: none;
  margin: 1.1rem 0 0;
  padding: 0;
}

.feedback-note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
  line-height: 1.5;
  margin: 0.55rem 0 0;
}

.feedback-list li {
  border-top: 1px solid var(--color-margin);
  font-family: var(--font-reading);
  line-height: 1.65;
  padding: 0.85rem 0 0.85rem 2rem;
  position: relative;
}

.feedback-list li::before {
  color: var(--color-rubric);
  content: '✦';
  left: 0.25rem;
  position: absolute;
}

.hymn-sheet {
  background:
    linear-gradient(
      90deg,
      transparent 0 2rem,
      color-mix(in srgb, var(--color-rule-gold) 28%, transparent) 2rem calc(2rem + 1px),
      transparent calc(2rem + 1px)
    ),
    var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  padding: clamp(1.5rem, 6vw, 3.5rem);
}

.hymn-sheet__meter {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  margin: 0.65rem 0 0;
  text-transform: uppercase;
}

.hymn-verses {
  display: grid;
  gap: 2rem;
  margin: 2.5rem auto 0;
  max-width: 31rem;
}

.hymn-verse {
  align-items: start;
  display: grid;
  gap: 1rem;
  grid-template-columns: 1.5rem 1fr;
}

.hymn-verse > span {
  color: var(--color-rubric);
  font-family: var(--font-display);
  font-size: 0.85rem;
  padding-top: 0.25rem;
}

.hymn-verse p {
  font-family: var(--font-reading);
  font-size: clamp(1.05rem, 2.5vw, 1.2rem);
  line-height: 1.75;
  margin: 0;
}

.tune-list {
  display: grid;
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
}

.tune-list li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  display: grid;
  gap: 0.75rem;
  grid-template-columns: minmax(9rem, 0.8fr) 1.4fr;
  padding: 1rem 0;
}

.tune-list strong {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.8rem;
  letter-spacing: 0.08em;
}

.tune-list span {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.92rem;
}

.artifact--empty > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.6;
}

.artifact__prose {
  font-family: var(--font-reading);
  font-size: 1.02rem;
  line-height: 1.75;
  margin-top: 1.4rem;
}

.artifact__prose--compact {
  color: color-mix(in srgb, var(--color-ink) 88%, var(--color-ink-muted));
  font-size: 0.92rem;
  line-height: 1.65;
  margin-top: 0;
}

.artifact__prose p + p {
  margin-top: 1rem;
}

.artifact__prose--compact p + p {
  margin-top: 0.65rem;
}

.scripture-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 0.9rem;
  margin-top: 1rem;
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
  margin: 1.1rem 0 0;
  padding: 0;
}

.outline li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  counter-increment: outline;
  display: grid;
  font-family: var(--font-reading);
  gap: 0.75rem 1rem;
  grid-template-columns: 2rem 3.4rem 1fr;
  line-height: 1.5;
  padding: 0.75rem 0;
}

.outline li::before {
  color: var(--color-rubric);
  content: counter(outline, upper-roman);
  font-family: var(--font-display);
  font-size: 0.78rem;
}

.outline__seek {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding: 0;
  text-align: left;
}

.outline__seek--empty {
  cursor: default;
  min-height: 1em;
}

.outline__seek:not(.outline__seek--empty):hover,
.outline__seek:not(.outline__seek--empty):focus-visible {
  text-decoration: underline;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1.25rem;
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

.empty-panel {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.98rem;
  line-height: 1.55;
  margin: 1.5rem 0 0;
}

.related-sermons {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
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

.transcript-controls {
  display: grid;
  gap: 0.85rem;
  margin-top: 1.25rem;
}

.transcript-view-toggle {
  border: 1px solid var(--color-margin);
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.15rem;
  padding: 0.2rem;
}

.transcript-view-toggle button,
.transcript-edition__toggle button {
  background: transparent;
  border: 0;
  color: var(--color-ink-muted);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  min-height: 2.35rem;
  padding: 0.4rem 0.65rem;
}

.transcript-view-toggle button.active,
.transcript-edition__toggle button.active {
  background: var(--color-lapis);
  color: var(--color-vellum-light);
}

.transcript-view-toggle button:focus-visible,
.transcript-edition__toggle button:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 2px;
}

.transcript-edition {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 0.85rem;
}

.transcript-edition__label {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.transcript-edition__toggle {
  border: 1px solid color-mix(in srgb, var(--color-margin) 70%, transparent);
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.1rem;
  padding: 0.15rem;
}

.transcript-edition__toggle button {
  font-size: 0.72rem;
  font-weight: 600;
  min-height: 2rem;
  min-width: 6.5rem;
}

.transcript-edition__toggle button.active {
  background: color-mix(in srgb, var(--color-lapis) 14%, var(--color-vellum-light));
  color: var(--color-lapis);
}

.transcript__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  line-height: 1.5;
  margin: 0.85rem 0 2.25rem;
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

.transcript__segment--virtual {
  content-visibility: auto;
  contain-intrinsic-size: auto 4.5rem;
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

.quiz {
  padding-top: 3rem;
}

.quiz-list {
  counter-reset: quiz-question;
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
}

.quiz-list > li {
  border-top: 1px solid var(--color-margin);
  counter-increment: quiz-question;
  padding: 1.25rem 0 1.25rem 2.5rem;
  position: relative;
}

.quiz-list > li::before {
  color: var(--color-rubric);
  content: counter(quiz-question);
  font-family: var(--font-display);
  left: 0.5rem;
  position: absolute;
  top: 1.4rem;
}

.quiz-list > li > p {
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.6;
  margin: 0;
}

.quiz-list details {
  margin-top: 0.75rem;
}

.quiz-list summary {
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
}

.quiz-list details p {
  background: color-mix(in srgb, var(--color-rule-gold) 9%, transparent);
  border-left: 2px solid var(--color-rule-gold);
  font-family: var(--font-reading);
  line-height: 1.6;
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
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

@media (max-width: 640px) {
  .sermon-detail--docked {
    padding-bottom: calc(13rem + env(safe-area-inset-bottom));
  }

  .audio-player--docked {
    bottom: calc(4.25rem + env(safe-area-inset-bottom));
    grid-template-columns: auto 1fr;
    justify-content: stretch;
    padding-bottom: 0.85rem;
  }

  .audio-player__track {
    display: none;
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

  .sermon-header__actions .sermon-header__regenerate {
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

  .question-set--kids {
    margin-inline: -0.75rem;
    padding: 1.5rem 0.75rem;
  }

  .hymn-sheet {
    background: var(--color-vellum-light);
    margin-inline: -0.75rem;
    padding-inline: 1.25rem;
  }

  .tune-list li {
    gap: 0.3rem;
    grid-template-columns: 1fr;
  }
}
</style>
