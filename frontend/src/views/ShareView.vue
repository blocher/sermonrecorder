<script setup lang="ts">
import { ref } from 'vue'
import { BookOpenText, CalendarDays, Clock3, MapPin, Pause, Play } from '@lucide/vue'
import BrandMark from '../components/BrandMark.vue'
import { getSermon } from '../data/sermons'

const sermon = getSermon('come-and-rest')
const playing = ref(false)
</script>

<template>
  <main class="share-page">
    <header class="share-header">
      <BrandMark />
      <span class="share-header__note">Shared sermon</span>
    </header>

    <article class="share-document">
      <header class="share-title page-gather">
        <p class="rubric-label">{{ sermon.liturgicalDay }}</p>
        <h1>{{ sermon.title }}</h1>
        <p class="share-title__preacher">{{ sermon.preacher }}</p>
        <div class="share-title__meta">
          <span><MapPin :size="15" aria-hidden="true" />{{ sermon.church }}</span>
          <span><CalendarDays :size="15" aria-hidden="true" />{{ sermon.date }}</span>
          <span><Clock3 :size="15" aria-hidden="true" />{{ sermon.duration }}</span>
        </div>
      </header>

      <section class="share-section share-section--lead page-gather">
        <p class="rubric-label">In brief</p>
        <p class="share-summary">{{ sermon.shortSummary }}</p>
      </section>

      <section class="share-section page-gather">
        <h2>Scripture</h2>
        <div class="share-scripture">
          <a v-for="reference in sermon.scripture" :key="reference" href="#" @click.prevent>
            <BookOpenText :size="18" :stroke-width="1.6" aria-hidden="true" />
            {{ reference }}
          </a>
        </div>
      </section>

      <section class="share-section page-gather">
        <h2>Outline</h2>
        <ol class="share-outline">
          <li v-for="item in sermon.outline" :key="item">{{ item }}</li>
        </ol>
      </section>

      <section class="share-section page-gather">
        <h2>Discussion</h2>
        <ol class="share-questions">
          <li v-for="question in sermon.adultQuestions" :key="question">{{ question }}</li>
        </ol>
      </section>

      <section class="share-section share-transcript page-gather">
        <p class="rubric-label">Cleaned transcript</p>
        <h2>Follow the sermon</h2>
        <div class="share-transcript__segments">
          <div v-for="segment in sermon.transcript" :key="segment.time">
            <button type="button">{{ segment.time }}</button>
            <p>{{ segment.text }}</p>
          </div>
        </div>
      </section>
    </article>

    <footer class="share-footer">
      <BrandMark compact />
      <p>This private link was shared by a Pewcorder listener.</p>
      <RouterLink to="/">Open Pewcorder</RouterLink>
    </footer>

    <section class="share-player" aria-label="Shared sermon audio">
      <button
        type="button"
        :aria-label="playing ? 'Pause sermon' : 'Play sermon'"
        @click="playing = !playing"
      >
        <Pause v-if="playing" :size="20" fill="currentColor" aria-hidden="true" />
        <Play v-else :size="20" fill="currentColor" aria-hidden="true" />
      </button>
      <div>
        <strong>{{ sermon.title }}</strong>
        <span>{{ playing ? 'Playing · 05:48' : `Listen · ${sermon.duration}` }}</span>
      </div>
      <div class="share-player__line" aria-hidden="true"><span></span></div>
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
