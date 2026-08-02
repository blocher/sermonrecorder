<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, ExternalLink } from '@lucide/vue'
import BrowseDetailModal from './BrowseDetailModal.vue'
import type { RelatedSource } from '../sermons/artifactContent'

const props = defineProps<{
  sources: RelatedSource[]
}>()

const openIndex = ref<number | null>(null)
const activeSource = computed(() =>
  openIndex.value === null ? null : (props.sources[openIndex.value] ?? null),
)

function openAt(index: number): void {
  openIndex.value = index
}

function close(): void {
  openIndex.value = null
}

function sourceKey(source: RelatedSource, index: number): string {
  return `${source.title}-${source.year}-${index}`
}

function metaLine(source: RelatedSource): string {
  return [source.author, source.year].filter(Boolean).join(' · ')
}
</script>

<template>
  <div v-if="sources.length" class="source-browse">
    <ul class="source-browse__list">
      <li v-for="(source, index) in sources" :key="sourceKey(source, index)">
        <button
          type="button"
          class="source-browse__row"
          :aria-label="`Open source: ${source.title}`"
          @click="openAt(index)"
        >
          <span class="source-browse__copy">
            <span class="source-browse__title">{{ source.title }}</span>
            <span v-if="metaLine(source)" class="source-browse__meta">
              {{ metaLine(source) }}
            </span>
            <span v-if="source.excerpt" class="source-browse__teaser">
              {{ source.excerpt }}
            </span>
          </span>
          <ChevronRight
            class="source-browse__chevron"
            :size="18"
            :stroke-width="1.7"
            aria-hidden="true"
          />
        </button>
      </li>
    </ul>

    <BrowseDetailModal
      :open="openIndex !== null"
      :index="openIndex ?? 0"
      :count="sources.length"
      labelled-by="related-source-detail-title"
      close-label="Close source"
      @close="close"
      @update:index="openIndex = $event"
    >
      <template v-if="activeSource">
        <p class="rubric-label">Related source</p>
        <h2 id="related-source-detail-title" class="source-browse__detail-title">
          <a
            v-if="activeSource.source_url"
            :href="activeSource.source_url"
            target="_blank"
            rel="noreferrer"
          >
            {{ activeSource.title }}
            <ExternalLink :size="16" :stroke-width="1.8" aria-hidden="true" />
          </a>
          <template v-else>{{ activeSource.title }}</template>
        </h2>
        <p v-if="metaLine(activeSource)" class="source-browse__detail-meta">
          {{ metaLine(activeSource) }}
        </p>
        <p v-if="activeSource.excerpt" class="source-browse__detail-excerpt">
          {{ activeSource.excerpt }}
        </p>
        <a
          v-if="activeSource.source_url"
          class="source-browse__open-link"
          :href="activeSource.source_url"
          target="_blank"
          rel="noreferrer"
        >
          Open original
          <ExternalLink :size="14" :stroke-width="1.8" aria-hidden="true" />
        </a>
      </template>
    </BrowseDetailModal>
  </div>
</template>

<style scoped>
.source-browse__list {
  display: grid;
  gap: 0.35rem;
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.source-browse__row {
  align-items: start;
  background: transparent;
  border: 0;
  border-left: 2px solid var(--color-rule-gold);
  color: inherit;
  cursor: pointer;
  display: grid;
  gap: 0.65rem;
  grid-template-columns: minmax(0, 1fr) auto;
  padding: 0.65rem 0.35rem 0.65rem 1rem;
  text-align: left;
  transition: background 140ms ease;
  width: 100%;
}

.source-browse__row:hover {
  background: color-mix(in srgb, var(--color-rule-gold) 8%, transparent);
}

.source-browse__row:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 2px;
}

.source-browse__copy {
  display: grid;
  gap: 0.28rem;
  min-width: 0;
}

.source-browse__title {
  font-family: var(--font-reading);
  font-size: 1.02rem;
  font-weight: 650;
  line-height: 1.35;
}

.source-browse__meta {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.source-browse__teaser {
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: var(--color-ink-muted);
  display: -webkit-box;
  font-family: var(--font-reading);
  font-size: 0.92rem;
  line-height: 1.45;
  overflow: hidden;
}

.source-browse__chevron {
  color: var(--color-ink-muted);
  flex-shrink: 0;
  margin-top: 0.2rem;
}

.source-browse__row:hover .source-browse__chevron {
  color: var(--color-lapis);
}

.source-browse__detail-title {
  font-family: var(--font-display);
  font-size: clamp(1.45rem, 4vw, 1.85rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 40;
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0.4rem 0 0;
}

.source-browse__detail-title a {
  align-items: baseline;
  color: var(--color-ink);
  display: inline-flex;
  gap: 0.4rem;
  text-decoration: none;
}

.source-browse__detail-title a:hover {
  color: var(--color-lapis);
}

.source-browse__detail-meta {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0.65rem 0 0;
  text-transform: uppercase;
}

.source-browse__detail-excerpt {
  font-family: var(--font-reading);
  font-size: 1.02rem;
  line-height: 1.65;
  margin: 1.15rem 0 0;
  white-space: pre-wrap;
}

.source-browse__open-link {
  align-items: center;
  color: var(--color-lapis);
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 700;
  gap: 0.35rem;
  letter-spacing: 0.04em;
  margin-top: 1.35rem;
  text-decoration: none;
  text-transform: uppercase;
}

.source-browse__open-link:hover {
  text-decoration: underline;
  text-underline-offset: 0.2rem;
}
</style>
