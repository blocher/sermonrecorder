<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  BookOpenText,
  CalendarDays,
  Clock3,
  Mail,
  MapPin,
  Pause,
  PencilLine,
  Play,
  RefreshCw,
  Share2,
} from '@lucide/vue'
import { getSermon } from '../data/sermons'

type Section = 'study' | 'transcript' | 'discuss' | 'reflection'

const route = useRoute()
const router = useRouter()
const sermon = computed(() => getSermon(String(route.params.id)))
const activeSection = ref<Section>('study')
const playing = ref(false)
const progress = ref(0.18)
let playbackTimer: number | undefined

const progressLabel = computed(() => `${Math.round(progress.value * 100)}%`)

function selectSection(section: Section) {
  activeSection.value = section
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function togglePlayback() {
  playing.value = !playing.value
}

function seekTo(seconds: number) {
  progress.value = Math.min(seconds / (32 * 60), 1)
  playing.value = true
}

watch(playing, (isPlaying) => {
  if (isPlaying) {
    playbackTimer = window.setInterval(() => {
      progress.value = Math.min(progress.value + 0.001, 1)
      if (progress.value >= 1) playing.value = false
    }, 1000)
  } else if (playbackTimer) {
    window.clearInterval(playbackTimer)
  }
})

onMounted(() => {
  if (route.hash === '#reflection') activeSection.value = 'reflection'
})

onBeforeUnmount(() => {
  if (playbackTimer) window.clearInterval(playbackTimer)
})
</script>

<template>
  <main class="sermon-detail page-gather">
    <button class="back-link" type="button" @click="router.push('/')">
      <ArrowLeft :size="17" :stroke-width="1.7" aria-hidden="true" />
      Library
    </button>

    <article>
      <header class="sermon-header">
        <div class="sermon-header__rubric">
          <span>{{ sermon.liturgicalDay }}</span>
          <span>Ready</span>
        </div>
        <h1>{{ sermon.title }}</h1>
        <p class="sermon-header__preacher">{{ sermon.preacher }}</p>
        <div class="sermon-header__meta">
          <span><MapPin :size="15" aria-hidden="true" />{{ sermon.church }}</span>
          <span><CalendarDays :size="15" aria-hidden="true" />{{ sermon.date }}</span>
          <span><Clock3 :size="15" aria-hidden="true" />{{ sermon.duration }}</span>
        </div>
        <div class="sermon-header__actions">
          <button type="button" @click="router.push('/share/pewcorder-preview')">
            <Share2 :size="17" aria-hidden="true" />
            Share page
          </button>
          <button type="button" @click="router.push(`/sermons/${sermon.id}/email`)">
            <Mail :size="17" aria-hidden="true" />
            Email
          </button>
        </div>
      </header>

      <section class="audio-player" aria-label="Sermon audio player">
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
            <span>{{ progressLabel }} · {{ sermon.duration }}</span>
          </div>
          <div class="audio-player__track" aria-hidden="true">
            <span :style="{ width: progressLabel }"></span>
          </div>
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

      <div class="sermon-content">
        <template v-if="activeSection === 'study'">
          <section class="artifact artifact--lead">
            <div class="artifact__heading">
              <p class="rubric-label">In brief</p>
              <div class="artifact__tools">
                <button type="button" aria-label="Edit short summary"><PencilLine :size="16" /></button>
                <button type="button" aria-label="Regenerate short summary"><RefreshCw :size="16" /></button>
              </div>
            </div>
            <p class="artifact__summary">{{ sermon.shortSummary }}</p>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Scripture</h2>
              <div class="artifact__tools">
                <button type="button" aria-label="Edit Scripture references"><PencilLine :size="16" /></button>
              </div>
            </div>
            <div class="scripture-links">
              <a v-for="reference in sermon.scripture" :key="reference" href="#" @click.prevent>
                <BookOpenText :size="17" :stroke-width="1.6" aria-hidden="true" />
                {{ reference }}
              </a>
            </div>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Long summary</h2>
              <div class="artifact__tools">
                <button type="button" aria-label="Edit long summary"><PencilLine :size="16" /></button>
                <button type="button" aria-label="Regenerate long summary"><RefreshCw :size="16" /></button>
              </div>
            </div>
            <div class="artifact__prose">
              <p v-for="paragraph in sermon.longSummary" :key="paragraph">{{ paragraph }}</p>
            </div>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Outline</h2>
              <div class="artifact__tools">
                <button type="button" aria-label="Edit outline"><PencilLine :size="16" /></button>
                <button type="button" aria-label="Regenerate outline"><RefreshCw :size="16" /></button>
              </div>
            </div>
            <ol class="outline">
              <li v-for="item in sermon.outline" :key="item">
                <span>{{ item }}</span>
              </li>
            </ol>
          </section>

          <section class="artifact">
            <div class="artifact__heading">
              <h2>Tags</h2>
              <div class="artifact__tools">
                <button type="button" aria-label="Edit tags"><PencilLine :size="16" /></button>
              </div>
            </div>
            <div class="tag-list">
              <button v-for="tag in sermon.tags" :key="tag" type="button">{{ tag }}</button>
              <button class="tag-list__add" type="button">+ Add tag</button>
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
              <div class="artifact__tools">
                <button type="button" aria-label="Edit transcript"><PencilLine :size="16" /></button>
              </div>
            </div>
            <p class="transcript__note">Side conversations have been removed. Tap a timestamp to listen from that moment.</p>
            <div class="transcript__segments">
              <div v-for="segment in sermon.transcript" :key="segment.time" class="transcript__segment">
                <button type="button" @click="seekTo(segment.seconds)">{{ segment.time }}</button>
                <p>{{ segment.text }}</p>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="activeSection === 'discuss'">
          <section class="artifact question-set">
            <p class="rubric-label">Around the table</p>
            <h2>Discussion questions</h2>
            <ol>
              <li v-for="question in sermon.adultQuestions" :key="question">{{ question }}</li>
            </ol>
          </section>
          <section class="artifact question-set question-set--kids">
            <p class="rubric-label">With children</p>
            <h2>Questions for younger listeners</h2>
            <ol>
              <li v-for="question in sermon.kidsQuestions" :key="question">{{ question }}</li>
            </ol>
          </section>
        </template>

        <template v-else>
          <section id="reflection" class="artifact reflection">
            <p class="rubric-label">Private to you</p>
            <h2>Reflection</h2>
            <p class="reflection__prompt">Where is this sermon asking for one faithful action?</p>
            <textarea
              :value="sermon.reflection"
              rows="8"
              aria-label="Your private reflection"
              placeholder="Begin writing…"
            ></textarea>
            <div class="reflection__footer">
              <span>Saved privately</span>
              <button type="button">Save reflection</button>
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

.artifact__tools {
  display: flex;
  flex: none;
  gap: 0.25rem;
}

.artifact__tools button {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-ink-muted);
  cursor: pointer;
  display: flex;
  height: 2.5rem;
  justify-content: center;
  width: 2.5rem;
}

.artifact__tools button:hover {
  color: var(--color-lapis);
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

.tag-list button {
  background: transparent;
  border: 0;
  border-bottom: 1px solid rgba(47, 75, 124, 0.35);
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  padding: 0.3rem 0;
}

.tag-list .tag-list__add {
  border-bottom-color: transparent;
  color: var(--color-ink-muted);
}

.transcript__note {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  line-height: 1.5;
  margin: 1rem 0 2.5rem;
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
