<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  BookOpenText,
  CalendarDays,
  Clock3,
  MapPin,
  Pause,
  Play,
  RefreshCw,
  UserRound,
} from '@lucide/vue'
import BrandMark from '../components/BrandMark.vue'
import DoctrinalFindingsList from '../components/DoctrinalFindingsList.vue'
import RelatedSourcesList from '../components/RelatedSourcesList.vue'
import SermonSectionTabs from '../components/SermonSectionTabs.vue'
import {
  isHtmlAudioAbortError,
  playHtmlAudio,
  waitForHtmlAudioCanPlay,
} from '../playback/htmlAudio'
import { seekRatioFromClientX } from '../playback/seekTrack'
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
  loadSharedSermon,
  serverSermonDuration,
  serverSermonTitle,
  type SharedSermonDetail,
  type StudyArtifactKind,
} from '../sermons/serverSermon'

const route = useRoute()
const sermon = ref<SharedSermonDetail>()
const sectionTabs = ref<InstanceType<typeof SermonSectionTabs>>()
const loading = ref(true)
const errorMessage = ref('')
const audio = ref<HTMLAudioElement>()
const playing = ref(false)
const currentSeconds = ref(0)
const playbackError = ref(false)
const refreshingAudio = ref(false)
const audioReloadToken = ref(0)
type AudioVariant = 'processed' | 'original'
const audioVariant = ref<AudioVariant>('original')
const scrubbing = ref(false)
const activeSection = ref<SermonSection>('study')
let robotsMeta: HTMLMetaElement | null = null
let previousRobotsContent: string | null = null

const transcriptLayout = ref<'timeline' | 'reading'>('timeline')

const progress = computed(() =>
  sermon.value ? Math.min(currentSeconds.value / sermon.value.duration_seconds, 1) : 0,
)
const progressPercent = computed(() => `${Math.round(progress.value * 100)}%`)
const activeAudioUrl = computed(() => {
  const current = sermon.value
  if (!current) return ''
  if (!current.has_playback_audio) return current.audio_url
  if (audioVariant.value === 'original') return current.original_audio_url
  return current.playback_audio_url || current.audio_url
})
const hymn = computed(() => parseHymn(artifact('hymn')))
const hymnTunes = computed(() => parseTuneSuggestions(artifact('hymn_tune_suggestions')))
const quiz = computed(() => parseQuiz(artifact('quiz')))
const outlinePoints = computed(() => parseOutlinePoints(artifact('outline')))
const relatedSources = computed(() => parseRelatedSources(artifact('related_sources')))
const doctrinalReview = computed(() => parseDoctrinalReview(artifact('doctrinal_review')))
const displayTranscriptSegments = computed(() => {
  const transcript = sermon.value?.transcript
  if (!transcript) return []
  return transcript.display_segments?.length
    ? transcript.display_segments
    : transcript.segments
})
const readingTranscriptParagraphs = computed(() => {
  const transcript = sermon.value?.transcript
  const segments = displayTranscriptSegments.value
  if (!segments.length) {
    const text = (transcript?.display_text || transcript?.text || '').trim()
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
const transcriptViewMeta = computed(() =>
  transcriptLayout.value === 'timeline'
    ? {
        rubric: 'Polished for listening',
        note: 'Tap a timestamp to listen from that moment.',
      }
    : {
        rubric: 'Polished for reading',
        note: 'Gathered into longer paragraphs for easier reading.',
      },
)
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

function artifact(kind: StudyArtifactKind): string {
  return sermon.value?.study_artifacts.find((candidate) => candidate.kind === kind)?.content ?? ''
}

function timestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}

function scriptureUrl(display: string): string {
  return `https://www.biblegateway.com/passage/?search=${encodeURIComponent(display)}`
}

function occasionLabel(kind: SharedSermonDetail['occasion_kind']): string {
  if (!kind) return ''
  return {
    sunday: 'Sunday',
    feast: 'Feast or holy day',
    wedding: 'Wedding',
    funeral: 'Funeral',
    midweek: 'Midweek service',
    other: 'Other occasion',
  }[kind]
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
  try {
    await playHtmlAudio(element)
  } catch (error) {
    if (isHtmlAudioAbortError(error)) return
    playing.value = false
    playbackError.value = true
  }
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
  const wasPlaying = playing.value
  const position = audio.value?.currentTime ?? currentSeconds.value
  audioVariant.value = variant
  playbackError.value = false
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

async function refreshSharedAudio(): Promise<void> {
  const token = String(route.params.token)
  if (!token || refreshingAudio.value) return
  const position = audio.value?.currentTime ?? currentSeconds.value
  refreshingAudio.value = true
  playbackError.value = false
  audio.value?.pause()
  playing.value = false
  try {
    sermon.value = await loadSharedSermon(token)
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
    playbackError.value = true
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

async function load(token: string): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  sermon.value = undefined
  activeSection.value = 'study'
  try {
    sermon.value = await loadSharedSermon(token)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'This shared Sermon is unavailable.'
  } finally {
    loading.value = false
  }
}

watch(
  () => String(route.params.token),
  (token) => void load(token),
  { immediate: true },
)

onMounted(() => {
  document.documentElement.classList.add('share-lock')
  document.body.classList.add('share-lock')
  robotsMeta = document.querySelector('meta[name="robots"]')
  previousRobotsContent = robotsMeta?.getAttribute('content') ?? null
  if (!robotsMeta) {
    robotsMeta = document.createElement('meta')
    robotsMeta.name = 'robots'
    document.head.append(robotsMeta)
  }
  robotsMeta.content = 'noindex,nofollow'
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('share-lock')
  document.body.classList.remove('share-lock')
  if (!robotsMeta) return
  if (previousRobotsContent === null) robotsMeta.remove()
  else robotsMeta.content = previousRobotsContent
})
</script>

<template>
  <div class="share-shell">
    <div class="share-scroll">
      <header class="share-header">
        <BrandMark />
        <span class="share-header__note">Shared sermon</span>
      </header>

      <article v-if="loading" class="share-state" role="status">
        <p class="rubric-label">Shared sermon</p>
        <h1>Opening the illuminated page…</h1>
      </article>

      <article v-else-if="errorMessage" class="share-state share-state--error" role="alert">
        <p class="rubric-label">Link unavailable</p>
        <h1>{{ errorMessage }}</h1>
        <p>The Congregant may have revoked this unlisted link.</p>
      </article>

      <article v-else-if="sermon" class="share-document">
        <header class="share-title page-gather">
          <div class="share-title__rubric">
            <span>{{ sermon.liturgical_day || 'Shared sermon' }}</span>
            <span v-if="sermon.occasion_kind">{{ occasionLabel(sermon.occasion_kind) }}</span>
          </div>
          <h1>{{ serverSermonTitle(sermon) }}</h1>
          <div
            v-if="sermon.tag_suggestions.length"
            class="share-title__tags"
            aria-label="Tags"
          >
            <span v-for="tag in sermon.tag_suggestions" :key="tag" class="share-tag-chip">
              {{ tag }}
            </span>
          </div>
          <dl class="share-register" aria-label="Sermon details">
            <div class="share-register__entry">
              <dt><MapPin :size="15" aria-hidden="true" />Church</dt>
              <dd>
                <strong :class="{ 'is-unset': !sermon.church }">{{
                  sermon.church?.name || 'Not assigned'
                }}</strong>
                <small v-if="sermon.church?.address">{{ sermon.church.address }}</small>
              </dd>
            </div>
            <div class="share-register__entry">
              <dt><UserRound :size="15" aria-hidden="true" />Preacher</dt>
              <dd>
                <strong :class="{ 'is-unset': !sermon.preacher }">{{
                  sermon.preacher?.name || 'Not assigned'
                }}</strong>
              </dd>
            </div>
            <div class="share-register__entry">
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
            <div class="share-register__entry">
              <dt><CalendarDays :size="15" aria-hidden="true" />Heard</dt>
              <dd>
                <strong>{{ capturedDate }}</strong>
                <small>{{ capturedTime }}</small>
              </dd>
            </div>
            <div class="share-register__entry">
              <dt><Clock3 :size="15" aria-hidden="true" />Length</dt>
              <dd>
                <strong>{{ serverSermonDuration(sermon.duration_seconds) }}</strong>
              </dd>
            </div>
          </dl>
        </header>

        <SermonSectionTabs
          ref="sectionTabs"
          class="share-tabs"
          :active-section="activeSection"
          @select="selectSection"
        />

        <div
          :id="`sermon-panel-${activeSection}`"
          role="tabpanel"
          :aria-labelledby="`sermon-tab-${activeSection}`"
        >
        <template v-if="activeSection === 'study'">
          <section class="share-section share-section--summary page-gather">
            <div class="share-summary-brief">
              <p class="rubric-label">In brief</p>
              <p class="share-summary">{{ artifact('short_summary') }}</p>
            </div>
            <div class="share-summary-long">
              <div class="share-prose share-prose--compact">
                <p v-for="paragraph in paragraphs(artifact('long_summary'))" :key="paragraph">
                  {{ paragraph }}
                </p>
              </div>
            </div>
          </section>

          <section class="share-section page-gather">
            <h2>Outline</h2>
            <ol class="share-outline">
              <li v-for="(point, index) in outlinePoints" :key="`${index}-${point.text}`">
                <button
                  v-if="point.start_seconds != null"
                  type="button"
                  class="share-outline__seek"
                  :aria-label="`Play from ${timestamp(point.start_seconds)}`"
                  @click="seekTo(point.start_seconds)"
                >
                  {{ timestamp(point.start_seconds) }}
                </button>
                <span
                  v-else
                  class="share-outline__seek share-outline__seek--empty"
                  aria-hidden="true"
                ></span>
                <span>{{ point.text }}</span>
              </li>
            </ol>
          </section>

          <section
            v-if="artifact('quotations')"
            class="share-section share-quotations page-gather"
          >
            <p class="rubric-label">In the preacher’s words</p>
            <h2>Quotations</h2>
            <div>
              <blockquote
                v-for="quotation in quotationItems(artifact('quotations'))"
                :key="quotation"
              >
                <p>{{ quotation }}</p>
              </blockquote>
            </div>
          </section>

          <section
            v-if="artifact('call_to_action') || artifact('practical_next_steps')"
            class="share-section share-section--call page-gather"
          >
            <h2>Action Items</h2>
            <p v-if="artifact('call_to_action')">{{ artifact('call_to_action') }}</p>
            <div v-if="artifact('practical_next_steps')" class="share-carry">
              <p class="rubric-label">Carry this with you</p>
              <ol class="share-practical">
                <li v-for="item in numberedItems(artifact('practical_next_steps'))" :key="item">
                  {{ item }}
                </li>
              </ol>
            </div>
          </section>

          <section class="share-section page-gather">
            <h2>Scripture</h2>
            <div v-if="sermon.scripture_references.length" class="share-scripture">
              <a
                v-for="reference in sermon.scripture_references"
                :key="reference.display"
                :href="scriptureUrl(reference.display)"
                target="_blank"
                rel="noreferrer"
              >
                <BookOpenText :size="18" :stroke-width="1.6" aria-hidden="true" />
                {{ reference.display }}
              </a>
            </div>
            <p v-else class="share-empty-copy">No Scripture references for this sermon.</p>
          </section>

          <section
            v-if="artifact('related_sources')"
            class="share-section share-sources page-gather"
          >
            <p class="rubric-label">For further study</p>
            <h2>Related sources</h2>
            <p class="share-feedback__note">
              Sources suggested via Magisterium AI Search. Confirm relevance before relying on them.
            </p>
            <RelatedSourcesList
              v-if="relatedSources.length"
              :sources="relatedSources"
            />
            <p v-else class="share-feedback__note">No related sources were suggested.</p>
          </section>
        </template>

        <template v-else-if="activeSection === 'feedback'">
          <section
            v-if="artifact('sermon_feedback')"
            class="share-section share-feedback page-gather"
          >
            <p class="rubric-label">If this sermon were revised</p>
            <h2>Craft feedback</h2>
            <p class="share-feedback__note">
              Suggestions for conveying the message more clearly — structure, missing points,
              tangents, and application. Not a doctrinal audit.
            </p>
            <ol>
              <li v-for="item in numberedItems(artifact('sermon_feedback'))" :key="item">
                {{ item }}
              </li>
            </ol>
          </section>

          <section
            v-if="artifact('doctrinal_review')"
            class="share-section share-doctrinal page-gather"
          >
            <p class="rubric-label">Catholic teaching check</p>
            <h2>Doctrinal review</h2>
            <p class="share-feedback__note">
              Advisory only. Verify every judgment against Scripture and the Church’s Magisterium.
              Generated citations can miss context.
            </p>
            <DoctrinalFindingsList
              :findings="doctrinalReview.findings"
              :empty-summary="doctrinalReview.summary"
            />
          </section>

          <p
            v-if="!artifact('sermon_feedback') && !artifact('doctrinal_review')"
            class="share-section share-empty-copy page-gather"
          >
            Feedback is not available for this sermon yet.
          </p>
        </template>

        <template v-else-if="activeSection === 'hymn'">
          <section v-if="artifact('hymn')" class="share-section share-hymn page-gather">
            <p class="rubric-label">Inspired by this sermon</p>
            <h2>{{ hymn.title || 'Hymn' }}</h2>
            <p v-if="hymn.meter" class="share-hymn__meter">Meter · {{ hymn.meter }}</p>
            <div class="share-hymn__verses">
              <div v-for="(verse, index) in hymn.verses" :key="index">
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
            class="share-section share-tunes page-gather"
          >
            <p class="rubric-label">Sing it with</p>
            <h2>Compatible tunes</h2>
            <ul>
              <li v-for="tune in hymnTunes" :key="tune.name">
                <strong>{{ tune.name }}</strong>
                <span>{{ tune.traditions }}</span>
              </li>
            </ul>
          </section>
          <section
            v-if="!artifact('hymn') && !artifact('hymn_tune_suggestions')"
            class="share-section share-empty page-gather"
          >
            <p class="rubric-label">Earlier sermon</p>
            <h2>No hymn was generated</h2>
            <p>Hymns are included when newly uploaded Sermons are prepared.</p>
          </section>
        </template>

        <template v-else-if="activeSection === 'discuss'">
          <section class="share-section page-gather">
            <p class="rubric-label">Around the table</p>
            <h2>Discussion questions</h2>
            <ol class="share-questions">
              <li
                v-for="question in numberedItems(artifact('adult_discussion_questions'))"
                :key="question"
              >
                {{ question }}
              </li>
            </ol>
          </section>

          <section class="share-section page-gather">
            <p class="rubric-label">With children</p>
            <h2>Questions for younger listeners</h2>
            <ol class="share-questions">
              <li
                v-for="question in numberedItems(artifact('kids_discussion_questions'))"
                :key="question"
              >
                {{ question }}
              </li>
            </ol>
          </section>

          <section v-if="artifact('quiz')" class="share-section share-quiz page-gather">
            <p class="rubric-label">Check the takeaways</p>
            <h2>Comprehension quiz</h2>
            <ol>
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

        <template v-else-if="activeSection === 'transcript'">
          <section class="share-section share-transcript page-gather">
            <p class="rubric-label">{{ transcriptViewMeta.rubric }}</p>
            <h2>Follow the sermon</h2>
            <div class="share-transcript-toggle" role="group" aria-label="Transcript layout">
              <button
                type="button"
                :class="{ active: transcriptLayout === 'timeline' }"
                :aria-pressed="transcriptLayout === 'timeline'"
                @click="transcriptLayout = 'timeline'"
              >
                Timeline
              </button>
              <button
                type="button"
                :class="{ active: transcriptLayout === 'reading' }"
                :aria-pressed="transcriptLayout === 'reading'"
                @click="transcriptLayout = 'reading'"
              >
                Reading
              </button>
            </div>
            <p class="share-transcript__note">{{ transcriptViewMeta.note }}</p>
            <div v-if="transcriptLayout === 'timeline'" class="share-transcript__segments">
              <div
                v-for="segment in displayTranscriptSegments"
                :key="`${segment.start_seconds}-${segment.text}`"
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
            <div v-else class="share-transcript__reading">
              <p v-for="(paragraph, index) in readingTranscriptParagraphs" :key="index">
                {{ paragraph }}
              </p>
            </div>
          </section>
        </template>
      </div>
    </article>

    <footer class="share-footer">
      <BrandMark compact />
      <p>This unlisted link was shared by a Pewcorder Congregant.</p>
      <RouterLink to="/">Open Pewcorder</RouterLink>
    </footer>
    </div>

    <section v-if="sermon" class="share-player" aria-label="Shared sermon audio">
      <audio
        :key="`${activeAudioUrl}:${audioReloadToken}`"
        ref="audio"
        :src="activeAudioUrl"
        preload="metadata"
        @play="playing = true"
        @pause="playing = false"
        @ended="playing = false"
        @timeupdate="currentSeconds = scrubbing ? currentSeconds : (audio?.currentTime ?? 0)"
        @error="playbackError = true"
      ></audio>
      <button
        type="button"
        :aria-label="playing ? 'Pause sermon' : 'Play sermon'"
        @click="togglePlayback"
      >
        <Pause v-if="playing" :size="20" fill="currentColor" aria-hidden="true" />
        <Play v-else :size="20" fill="currentColor" aria-hidden="true" />
      </button>
      <div>
        <strong>{{ serverSermonTitle(sermon) }}</strong>
        <span v-if="!playbackError">
          {{ playing ? 'Playing' : 'Listen' }} · {{ timestamp(currentSeconds) }} /
          {{ serverSermonDuration(sermon.duration_seconds) }}
        </span>
        <div v-else class="share-player__error" role="alert">
          <span>Audio could not be played. Refresh and try again.</span>
          <button
            type="button"
            class="share-player__refresh"
            :disabled="refreshingAudio"
            aria-label="Refresh shared audio"
            @click="refreshSharedAudio"
          >
            <RefreshCw
              :size="14"
              :class="{ 'is-spinning': refreshingAudio }"
              aria-hidden="true"
            />
          </button>
        </div>
        <div
          v-if="sermon.has_playback_audio"
          class="share-player__variants"
          role="group"
          aria-label="Optional audio version"
        >
          <button
            type="button"
            :aria-pressed="audioVariant === 'original'"
            :class="{ 'is-active': audioVariant === 'original' }"
            @click="setAudioVariant('original')"
          >
            Original
          </button>
          <button
            type="button"
            :aria-pressed="audioVariant === 'processed'"
            :class="{ 'is-active': audioVariant === 'processed' }"
            @click="setAudioVariant('processed')"
          >
            Isolated Speaker Voice
          </button>
        </div>
      </div>
      <div
        class="share-player__line"
        role="slider"
        tabindex="0"
        aria-label="Shared Sermon playback position"
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
  </div>
</template>

<style scoped>
.share-shell {
  background:
    linear-gradient(90deg, transparent 0 6%, rgba(184, 150, 62, 0.12) 6% calc(6% + 1px), transparent calc(6% + 1px)),
    var(--color-vellum);
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.share-scroll {
  -webkit-overflow-scrolling: touch;
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: none;
}

.share-header {
  align-items: center;
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  justify-content: space-between;
  margin: 0 auto;
  max-width: 72rem;
  padding: 1.5rem clamp(1.25rem, 5vw, 3.5rem);
  width: 100%;
}

.share-header__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.share-state {
  margin: 0 auto;
  max-width: 46rem;
  padding: 7rem clamp(1.5rem, 7vw, 4.5rem);
}

.share-state h1 {
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 7vw, 4.8rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 43;
  font-weight: 500;
  letter-spacing: -0.05em;
  line-height: 1;
  margin: 0.8rem 0 1rem;
}

.share-state p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
}

.share-state--error .rubric-label {
  color: var(--color-rubric);
}

.share-document {
  margin: 0 auto;
  max-width: 46rem;
  padding: 5rem clamp(1.5rem, 7vw, 4.5rem) 0;
}

.share-title {
  padding-bottom: 0.5rem;
}

.share-title__rubric {
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

.share-title__rubric span + span::before {
  color: var(--color-rule-gold);
  content: '·';
  margin-right: 0.75rem;
}

.share-title h1 {
  font-family: var(--font-display);
  font-size: clamp(3.3rem, 11vw, 6.8rem);
  font-variation-settings: 'opsz' 100, 'SOFT' 43;
  font-weight: 500;
  letter-spacing: -0.065em;
  line-height: 0.9;
  margin: 0.8rem 0 0;
}

.share-title__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 1rem 0 0;
}

.share-tag-chip {
  align-items: center;
  background: color-mix(in srgb, var(--color-lapis) 8%, var(--color-vellum));
  border: 1px solid color-mix(in srgb, var(--color-lapis) 28%, var(--color-margin));
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.74rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  line-height: 1;
  padding: 0.42rem 0.7rem;
}

.share-register {
  background: color-mix(in srgb, var(--color-vellum-light) 82%, transparent);
  border-bottom: 1px solid var(--color-rule-gold);
  border-top: 1px solid var(--color-rule-gold);
  display: grid;
  grid-template-columns: 1.35fr 1fr 1.2fr 1fr 0.7fr;
  margin: 1.35rem 0 0;
}

.share-register__entry {
  min-width: 0;
  padding: 1rem clamp(0.7rem, 2vw, 1.15rem);
}

.share-register__entry + .share-register__entry {
  border-left: 1px solid var(--color-margin);
}

.share-register dt {
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

.share-register dd {
  margin: 0.55rem 0 0;
}

.share-register strong,
.share-register small {
  display: block;
  overflow-wrap: anywhere;
}

.share-register strong {
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.3;
}

.share-register strong.is-unset {
  color: var(--color-ink-muted);
  font-style: italic;
  font-weight: 400;
}

.share-register small {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.69rem;
  line-height: 1.35;
  margin-top: 0.25rem;
}

.share-empty-copy {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-style: italic;
  line-height: 1.55;
  margin: 1.3rem 0 0;
}

.share-tabs {
  margin-top: 1.25rem;
}

.share-section {
  border-bottom: 1px solid var(--color-margin);
  padding: 3.5rem 0;
}

.share-section h2 {
  font-family: var(--font-display);
  font-size: 2.15rem;
  font-variation-settings: 'opsz' 42, 'SOFT' 48;
  font-weight: 540;
  letter-spacing: -0.035em;
  margin: 0;
}

.share-summary {
  font-family: var(--font-reading);
  font-size: clamp(1.25rem, 3vw, 1.55rem);
  line-height: 1.65;
  margin: 0.8rem 0 0;
}

.share-section--summary {
  display: grid;
  gap: 0.85rem;
}

.share-summary-long {
  border-top: 1px solid color-mix(in srgb, var(--color-margin) 70%, transparent);
  padding-top: 0.85rem;
}

.share-prose--compact {
  color: color-mix(in srgb, var(--color-ink) 88%, var(--color-ink-muted));
  font-size: 0.92rem;
  line-height: 1.65;
  margin-top: 0;
}

.share-prose--compact p {
  font-size: inherit;
  line-height: inherit;
}

.share-prose--compact p + p {
  margin-top: 0.65rem;
}

.share-quotations > div {
  display: grid;
  gap: 1.35rem;
  margin-top: 1.5rem;
}

.share-quotations blockquote {
  border-left: 2px solid var(--color-rule-gold);
  margin: 0;
  padding: 0.15rem 0 0.15rem clamp(1rem, 5vw, 1.75rem);
}

.share-quotations blockquote p {
  font-family: var(--font-reading);
  font-size: clamp(1.22rem, 3vw, 1.52rem);
  font-style: italic;
  line-height: 1.58;
  margin: 0;
}

.share-quotations blockquote p::before,
.share-quotations blockquote p::after {
  color: var(--color-rubric);
  font-family: var(--font-display);
  font-style: normal;
}

.share-quotations blockquote p::before {
  content: '“';
}

.share-quotations blockquote p::after {
  content: '”';
}

.share-section--call {
  background: color-mix(in srgb, var(--color-rule-gold) 11%, var(--color-vellum-light));
  border: 1px solid color-mix(in srgb, var(--color-rule-gold) 55%, var(--color-margin));
  margin-top: 2.5rem;
  padding: clamp(1.5rem, 5vw, 2.5rem);
}

.share-section--call > p {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 2.6vw, 1.45rem);
  letter-spacing: -0.02em;
  line-height: 1.35;
  margin: 1rem 0 0;
}

.share-carry {
  border-top: 1px solid color-mix(in srgb, var(--color-rule-gold) 35%, var(--color-margin));
  margin-top: 1.25rem;
  padding-top: 0.95rem;
}

.share-carry .share-practical {
  margin-top: 0.75rem;
}

.share-prose {
  margin-top: 1.4rem;
}

.share-prose p {
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.75;
  margin: 0;
}

.share-prose p + p {
  margin-top: 1rem;
}

.share-scripture {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  margin-top: 1.4rem;
}

.share-scripture a {
  align-items: center;
  border-bottom: 1px solid rgba(47, 75, 124, 0.45);
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-reading);
  gap: 0.5rem;
  padding-bottom: 0.25rem;
  text-decoration: none;
}

.share-outline,
.share-practical,
.share-questions {
  list-style: none;
  margin: 1.7rem 0 0;
  padding: 0;
}

.share-outline {
  counter-reset: share-outline;
}

.share-practical li {
  border-left: 2px solid var(--color-rule-gold);
  font-family: var(--font-reading);
  line-height: 1.6;
  padding: 0.45rem 0 0.45rem 1rem;
}

.share-practical li + li {
  margin-top: 0.8rem;
}

.share-outline li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  counter-increment: share-outline;
  display: grid;
  font-family: var(--font-reading);
  gap: 0.75rem 1rem;
  grid-template-columns: 2rem 3.4rem 1fr;
  line-height: 1.55;
  padding: 1rem 0;
}

.share-outline li::before {
  color: var(--color-rubric);
  content: counter(share-outline, upper-roman);
  font-family: var(--font-display);
  font-size: 0.78rem;
}

.share-outline__seek {
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

.share-outline__seek--empty {
  cursor: default;
  min-height: 1em;
}

.share-outline__seek:not(.share-outline__seek--empty):hover,
.share-outline__seek:not(.share-outline__seek--empty):focus-visible {
  text-decoration: underline;
}

.share-feedback {
  background: color-mix(in srgb, var(--color-lapis) 5%, var(--color-vellum-light));
  border: 1px solid color-mix(in srgb, var(--color-lapis) 22%, var(--color-margin));
  margin-top: 3.5rem;
  padding: clamp(1.5rem, 5vw, 2.4rem);
}

.share-feedback ol,
.share-quiz ol {
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
}

.share-feedback__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
  line-height: 1.5;
  margin: 0.8rem 0 0;
}

.share-feedback li {
  border-top: 1px solid var(--color-margin);
  font-family: var(--font-reading);
  line-height: 1.65;
  padding: 1rem 0 1rem 2rem;
  position: relative;
}

.share-feedback li::before {
  color: var(--color-rubric);
  content: '✦';
  left: 0.25rem;
  position: absolute;
}

.share-hymn {
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

.share-hymn__meter {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  margin: 0.65rem 0 0;
  text-transform: uppercase;
}

.share-hymn__verses {
  display: grid;
  gap: 2rem;
  margin: 2.5rem auto 0;
  max-width: 31rem;
}

.share-hymn__verses > div {
  align-items: start;
  display: grid;
  gap: 1rem;
  grid-template-columns: 1.5rem 1fr;
}

.share-hymn__verses span {
  color: var(--color-rubric);
  font-family: var(--font-display);
  font-size: 0.85rem;
  padding-top: 0.25rem;
}

.share-hymn__verses p {
  font-family: var(--font-reading);
  font-size: clamp(1.05rem, 2.5vw, 1.2rem);
  line-height: 1.75;
  margin: 0;
}

.share-tunes ul {
  display: grid;
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
}

.share-tunes li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  display: grid;
  gap: 0.75rem;
  grid-template-columns: minmax(9rem, 0.8fr) 1.4fr;
  padding: 1rem 0;
}

.share-tunes strong {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.8rem;
  letter-spacing: 0.08em;
}

.share-tunes span,
.share-empty > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.92rem;
}

.share-questions {
  counter-reset: share-question;
}

.share-questions li {
  border-top: 1px solid var(--color-margin);
  counter-increment: share-question;
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.6;
  padding: 1rem 0 1rem 2.3rem;
  position: relative;
}

.share-questions li::before {
  color: var(--color-rubric);
  content: counter(share-question);
  font-family: var(--font-display);
  left: 0.4rem;
  position: absolute;
}

.share-quiz ol {
  counter-reset: share-quiz;
}

.share-quiz li {
  border-top: 1px solid var(--color-margin);
  counter-increment: share-quiz;
  padding: 1.25rem 0 1.25rem 2.5rem;
  position: relative;
}

.share-quiz li::before {
  color: var(--color-rubric);
  content: counter(share-quiz);
  font-family: var(--font-display);
  left: 0.5rem;
  position: absolute;
  top: 1.4rem;
}

.share-quiz li > p {
  font-family: var(--font-reading);
  font-size: 1.05rem;
  line-height: 1.6;
  margin: 0;
}

.share-quiz details {
  margin-top: 0.75rem;
}

.share-quiz summary {
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
}

.share-quiz details p {
  background: color-mix(in srgb, var(--color-rule-gold) 9%, transparent);
  border-left: 2px solid var(--color-rule-gold);
  font-family: var(--font-reading);
  line-height: 1.6;
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
}

.share-transcript h2 {
  margin-top: 0.5rem;
}

.share-transcript__segments {
  margin-top: 2rem;
}

.share-transcript__segments > div {
  align-items: baseline;
  display: grid;
  gap: 1rem;
  grid-template-columns: 3.2rem 1fr;
}

.share-transcript__segments > div + div {
  margin-top: 1.4rem;
}

.share-transcript__segments button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.74rem;
  font-weight: 650;
  padding: 0;
}

.share-transcript__segments p {
  font-family: var(--font-reading);
  font-size: 1.06rem;
  line-height: 1.72;
  margin: 0;
}

.share-transcript-toggle {
  border: 1px solid var(--color-margin);
  display: grid;
  gap: 0.15rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 1.25rem;
  max-width: 18rem;
  padding: 0.2rem;
}

.share-transcript-toggle button {
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

.share-transcript-toggle button.active {
  background: var(--color-lapis);
  color: var(--color-vellum-light);
}

.share-transcript__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  line-height: 1.5;
  margin: 0.85rem 0 2rem;
}

.share-transcript__reading {
  display: grid;
  gap: 1.1rem;
}

.share-transcript__reading p {
  font-family: var(--font-reading);
  font-size: 1.06rem;
  line-height: 1.72;
  margin: 0;
}

.share-footer {
  align-items: center;
  display: flex;
  flex-direction: column;
  margin: 4rem auto 2.5rem;
  max-width: 40rem;
  padding: 2rem 1.5rem;
  text-align: center;
}

.share-footer p {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  margin: 0.8rem 0;
}

.share-footer a {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.8rem;
  font-weight: 650;
  text-underline-offset: 0.25rem;
}

.share-player {
  align-items: center;
  background: color-mix(in srgb, var(--color-ink) 96%, transparent);
  box-shadow: 0 -10px 30px rgba(28, 36, 48, 0.17);
  color: var(--color-vellum);
  display: grid;
  flex: none;
  gap: 1rem;
  grid-template-columns: auto minmax(8rem, auto) minmax(5rem, 20rem);
  justify-content: center;
  padding: 0.85rem 1rem calc(0.85rem + env(safe-area-inset-bottom));
  width: 100%;
  z-index: 20;
}

.share-player audio {
  display: none;
}

.share-player > button {
  align-items: center;
  background: var(--color-vellum);
  border: 0;
  border-radius: 50%;
  color: var(--color-rubric);
  cursor: pointer;
  display: flex;
  height: 2.7rem;
  justify-content: center;
  width: 2.7rem;
}

.share-player strong,
.share-player span {
  display: block;
  font-family: var(--font-utility);
}

.share-player strong {
  font-size: 0.78rem;
  font-weight: 650;
}

.share-player span {
  color: rgba(241, 238, 228, 0.65);
  font-size: 0.7rem;
  margin-top: 0.15rem;
}

.share-player__error {
  align-items: center;
  color: color-mix(in srgb, #f1eee4 72%, var(--color-rubric));
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.7rem;
  gap: 0.4rem;
  margin-top: 0.2rem;
}

.share-player__refresh {
  align-items: center;
  background: rgba(241, 238, 228, 0.12);
  border: 1px solid rgba(241, 238, 228, 0.28);
  border-radius: 999px;
  color: inherit;
  display: inline-flex;
  flex: 0 0 auto;
  justify-content: center;
  min-height: 1.65rem;
  min-width: 1.65rem;
  padding: 0.2rem;
}

.share-player__refresh:disabled {
  opacity: 0.7;
}

.share-player__refresh .is-spinning {
  animation: share-refresh-spin 0.9s linear infinite;
}

@keyframes share-refresh-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .share-player__refresh .is-spinning {
    animation: none;
  }
}

.share-player__variants {
  display: inline-flex;
  gap: 0.2rem;
  margin-top: 0.45rem;
}

.share-player__variants button {
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

.share-player__variants button.is-active {
  background: var(--color-vellum);
  border-color: var(--color-vellum);
  color: var(--color-ink);
}

.share-player__line {
  background: rgba(241, 238, 228, 0.2);
  cursor: pointer;
  height: 12px;
  padding: 5px 0;
  touch-action: none;
}

.share-player__line span {
  background: var(--color-rule-gold);
  display: block;
  height: 2px;
  margin: 0;
  position: relative;
  width: 18%;
}

@media (max-width: 800px) {
  .share-register {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .share-register__entry + .share-register__entry {
    border-left: 0;
  }

  .share-register__entry:nth-child(even) {
    border-left: 1px solid var(--color-margin);
  }

  .share-register__entry:nth-child(n + 3) {
    border-top: 1px solid var(--color-margin);
  }

  .share-register__entry:last-child {
    grid-column: 1 / -1;
  }
}

@media (max-width: 600px) {
  .share-shell {
    background: var(--color-vellum);
  }

  .share-header {
    padding-block: 1.1rem;
  }

  .share-document {
    padding-top: 3.5rem;
  }

  .share-title h1 {
    font-size: clamp(3.5rem, 17vw, 5.5rem);
  }

  .share-hymn {
    background: var(--color-vellum-light);
    margin-inline: -0.75rem;
    padding-inline: 1.25rem;
  }

  .share-tunes li {
    gap: 0.3rem;
    grid-template-columns: 1fr;
  }

  .share-player {
    grid-template-columns: auto 1fr;
    justify-content: stretch;
  }

  .share-player__line {
    display: none;
  }
}

@media (prefers-reduced-motion: no-preference) {
  .share-document {
    animation: ink-arrive 550ms ease both;
  }

  @keyframes ink-arrive {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
}
</style>
