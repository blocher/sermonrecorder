<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BookOpenText, CalendarDays, Clock3, Pause, Play } from '@lucide/vue'
import BrandMark from '../components/BrandMark.vue'
import {
  loadSharedSermon,
  serverSermonDuration,
  serverSermonTitle,
  type SharedSermonDetail,
  type StudyArtifactKind,
} from '../sermons/serverSermon'

const route = useRoute()
const sermon = ref<SharedSermonDetail>()
const loading = ref(true)
const errorMessage = ref('')
const audio = ref<HTMLAudioElement>()
const playing = ref(false)
const currentSeconds = ref(0)
const playbackError = ref(false)
let robotsMeta: HTMLMetaElement | null = null
let previousRobotsContent: string | null = null

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

async function load(token: string): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  sermon.value = undefined
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
  if (!robotsMeta) return
  if (previousRobotsContent === null) robotsMeta.remove()
  else robotsMeta.content = previousRobotsContent
})
</script>

<template>
  <main class="share-page">
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
        <p class="rubric-label">Shared sermon</p>
        <h1>{{ serverSermonTitle(sermon) }}</h1>
        <div class="share-title__meta">
          <span><CalendarDays :size="15" aria-hidden="true" />{{ capturedDate }}</span>
          <span>
            <Clock3 :size="15" aria-hidden="true" />{{
              serverSermonDuration(sermon.duration_seconds)
            }}
          </span>
        </div>
      </header>

      <section class="share-section share-section--lead page-gather">
        <p class="rubric-label">In brief</p>
        <p class="share-summary">{{ artifact('short_summary') }}</p>
      </section>

      <section v-if="sermon.scripture_references.length" class="share-section page-gather">
        <h2>Scripture</h2>
        <div class="share-scripture">
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
      </section>

      <section class="share-section page-gather">
        <h2>Long summary</h2>
        <div class="share-prose">
          <p v-for="paragraph in paragraphs(artifact('long_summary'))" :key="paragraph">
            {{ paragraph }}
          </p>
        </div>
      </section>

      <section class="share-section page-gather">
        <h2>Outline</h2>
        <ol class="share-outline">
          <li v-for="item in numberedItems(artifact('outline'))" :key="item">{{ item }}</li>
        </ol>
      </section>

      <section class="share-section page-gather">
        <h2>Discussion</h2>
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

      <section class="share-section share-transcript page-gather">
        <p class="rubric-label">Cleaned transcript</p>
        <h2>Follow the sermon</h2>
        <div class="share-transcript__segments">
          <div
            v-for="segment in sermon.transcript?.segments ?? []"
            :key="`${segment.start_seconds}-${segment.text}`"
          >
            <button type="button" @click="seekTo(segment.start_seconds)">
              {{ timestamp(segment.start_seconds) }}
            </button>
            <p>{{ segment.text }}</p>
          </div>
        </div>
      </section>
    </article>

    <footer class="share-footer">
      <BrandMark compact />
      <p>This unlisted link was shared by a Pewcorder listener.</p>
      <RouterLink to="/">Open Pewcorder</RouterLink>
    </footer>

    <section v-if="sermon" class="share-player" aria-label="Shared sermon audio">
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
        type="button"
        :aria-label="playing ? 'Pause sermon' : 'Play sermon'"
        @click="togglePlayback"
      >
        <Pause v-if="playing" :size="20" fill="currentColor" aria-hidden="true" />
        <Play v-else :size="20" fill="currentColor" aria-hidden="true" />
      </button>
      <div>
        <strong>{{ serverSermonTitle(sermon) }}</strong>
        <span>
          {{
            playbackError
              ? 'Audio unavailable'
              : `${playing ? 'Playing' : 'Listen'} · ${serverSermonDuration(sermon.duration_seconds)}`
          }}
        </span>
      </div>
      <div class="share-player__line" aria-hidden="true">
        <span :style="{ width: progressLabel }"></span>
      </div>
    </section>
  </main>
</template>

<style scoped>
.share-page {
  background:
    linear-gradient(90deg, transparent 0 6%, rgba(184, 150, 62, 0.12) 6% calc(6% + 1px), transparent calc(6% + 1px)),
    var(--color-vellum);
  min-height: 100svh;
  padding-bottom: 7rem;
}

.share-header {
  align-items: center;
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  justify-content: space-between;
  margin: 0 auto;
  max-width: 72rem;
  padding: 1.5rem clamp(1.25rem, 5vw, 3.5rem);
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
  border-bottom: 1px solid var(--color-rule-gold);
  padding-bottom: 3rem;
}

.share-title h1 {
  font-family: var(--font-display);
  font-size: clamp(3.3rem, 11vw, 6.8rem);
  font-variation-settings: 'opsz' 100, 'SOFT' 43;
  font-weight: 500;
  letter-spacing: -0.065em;
  line-height: 0.9;
  margin: 0.8rem 0 1.5rem;
}

.share-title__preacher {
  font-family: var(--font-reading);
  font-size: 1.15rem;
  font-style: italic;
}

.share-title__meta {
  color: var(--color-ink-muted);
  display: flex;
  flex-wrap: wrap;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  gap: 0.65rem 1.1rem;
  margin-top: 1.1rem;
}

.share-title__meta span {
  align-items: center;
  display: inline-flex;
  gap: 0.3rem;
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
.share-questions {
  list-style: none;
  margin: 1.7rem 0 0;
  padding: 0;
}

.share-outline {
  counter-reset: share-outline;
}

.share-outline li {
  align-items: baseline;
  border-top: 1px solid var(--color-margin);
  counter-increment: share-outline;
  display: grid;
  font-family: var(--font-reading);
  gap: 1rem;
  grid-template-columns: 2rem 1fr;
  line-height: 1.55;
  padding: 1rem 0;
}

.share-outline li::before {
  color: var(--color-rubric);
  content: counter(share-outline, upper-roman);
  font-family: var(--font-display);
  font-size: 0.78rem;
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

.share-footer {
  align-items: center;
  display: flex;
  flex-direction: column;
  margin: 4rem auto 0;
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
  bottom: 0;
  box-shadow: 0 -10px 30px rgba(28, 36, 48, 0.17);
  color: var(--color-vellum);
  display: grid;
  gap: 1rem;
  grid-template-columns: auto minmax(8rem, auto) minmax(5rem, 20rem);
  left: 50%;
  max-width: 42rem;
  padding: 0.85rem 1rem calc(0.85rem + env(safe-area-inset-bottom));
  position: fixed;
  transform: translateX(-50%);
  width: calc(100% - 2rem);
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

.share-player__line {
  background: rgba(241, 238, 228, 0.2);
  height: 2px;
}

.share-player__line span {
  background: var(--color-rule-gold);
  height: 100%;
  margin: 0;
  width: 18%;
}

@media (max-width: 600px) {
  .share-page {
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

  .share-player {
    grid-template-columns: auto 1fr;
    width: 100%;
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
