<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, ExternalLink } from '@lucide/vue'
import BrowseDetailModal from './BrowseDetailModal.vue'
import type { DoctrinalFinding } from '../sermons/artifactContent'

const props = defineProps<{
  findings: DoctrinalFinding[]
  emptySummary?: string
}>()

const openIndex = ref<number | null>(null)
const activeFinding = computed(() =>
  openIndex.value === null ? null : (props.findings[openIndex.value] ?? null),
)

function openAt(index: number): void {
  openIndex.value = index
}

function close(): void {
  openIndex.value = null
}

function citationCountLabel(count: number): string {
  return count === 1 ? '1 citation' : `${count} citations`
}
</script>

<template>
  <div v-if="findings.length" class="doctrinal-browse">
    <ul class="doctrinal-browse__list">
      <li v-for="(finding, index) in findings" :key="`${finding.assertion}-${index}`">
        <button
          type="button"
          class="doctrinal-browse__row"
          :aria-label="`Open finding: ${finding.assertion}`"
          @click="openAt(index)"
        >
          <span class="doctrinal-browse__copy">
            <span
              class="doctrinal-browse__severity"
              :data-severity="finding.severity"
            >
              {{ finding.severity }}
            </span>
            <span class="doctrinal-browse__assertion">{{ finding.assertion }}</span>
            <span v-if="finding.explanation" class="doctrinal-browse__teaser">
              {{ finding.explanation }}
            </span>
            <span v-if="finding.citations.length" class="doctrinal-browse__count">
              {{ citationCountLabel(finding.citations.length) }}
            </span>
          </span>
          <ChevronRight
            class="doctrinal-browse__chevron"
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
      :count="findings.length"
      labelled-by="doctrinal-finding-detail-title"
      close-label="Close finding"
      @close="close"
      @update:index="openIndex = $event"
    >
      <template v-if="activeFinding">
        <p
          class="doctrinal-browse__detail-severity"
          :data-severity="activeFinding.severity"
        >
          {{ activeFinding.severity }}
        </p>
        <h2 id="doctrinal-finding-detail-title" class="doctrinal-browse__detail-title">
          {{ activeFinding.assertion }}
        </h2>
        <p v-if="activeFinding.explanation" class="doctrinal-browse__detail-explanation">
          {{ activeFinding.explanation }}
        </p>
        <ul v-if="activeFinding.citations.length" class="doctrinal-browse__citations">
          <li
            v-for="citation in activeFinding.citations"
            :key="citation.document_title + citation.document_reference"
          >
            <strong>
              <a
                v-if="citation.source_url"
                :href="citation.source_url"
                target="_blank"
                rel="noreferrer"
              >
                {{ citation.document_title || 'Cited source' }}
                <ExternalLink :size="13" :stroke-width="1.8" aria-hidden="true" />
              </a>
              <template v-else>
                {{ citation.document_title || 'Cited source' }}
              </template>
            </strong>
            <span v-if="citation.document_author || citation.document_reference">
              —
              <template v-if="citation.document_author">
                {{ citation.document_author }}
              </template>
              <template v-if="citation.document_reference">
                §{{ citation.document_reference }}
              </template>
            </span>
            <p v-if="citation.cited_text">{{ citation.cited_text }}</p>
          </li>
        </ul>
      </template>
    </BrowseDetailModal>
  </div>
  <p v-else class="doctrinal-browse__empty">
    {{
      emptySummary ||
      'No assertions were flagged as heretical or borderline relative to Catholic teaching.'
    }}
  </p>
</template>

<style scoped>
.doctrinal-browse__list {
  display: grid;
  gap: 0.35rem;
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.doctrinal-browse__row {
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

.doctrinal-browse__row:hover {
  background: color-mix(in srgb, var(--color-rule-gold) 8%, transparent);
}

.doctrinal-browse__row:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 2px;
}

.doctrinal-browse__copy {
  display: grid;
  gap: 0.28rem;
  min-width: 0;
}

.doctrinal-browse__severity,
.doctrinal-browse__detail-severity {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0;
  text-transform: uppercase;
}

.doctrinal-browse__severity[data-severity='heretical'],
.doctrinal-browse__detail-severity[data-severity='heretical'] {
  color: #8a3b2d;
}

.doctrinal-browse__severity[data-severity='borderline'],
.doctrinal-browse__detail-severity[data-severity='borderline'] {
  color: #8a6a2d;
}

.doctrinal-browse__assertion {
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  display: -webkit-box;
  font-family: var(--font-reading);
  font-size: 1.02rem;
  font-weight: 650;
  line-height: 1.35;
  overflow: hidden;
}

.doctrinal-browse__teaser {
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: var(--color-ink-muted);
  display: -webkit-box;
  font-family: var(--font-reading);
  font-size: 0.92rem;
  line-height: 1.45;
  overflow: hidden;
}

.doctrinal-browse__count {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.doctrinal-browse__chevron {
  color: var(--color-ink-muted);
  flex-shrink: 0;
  margin-top: 0.2rem;
}

.doctrinal-browse__row:hover .doctrinal-browse__chevron {
  color: var(--color-lapis);
}

.doctrinal-browse__detail-title {
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 4vw, 1.75rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 40;
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin: 0.45rem 0 0;
}

.doctrinal-browse__detail-explanation {
  font-family: var(--font-reading);
  font-size: 1.02rem;
  line-height: 1.65;
  margin: 1.1rem 0 0;
  white-space: pre-wrap;
}

.doctrinal-browse__citations {
  display: grid;
  gap: 0.9rem;
  list-style: none;
  margin: 1.35rem 0 0;
  padding: 0.95rem 0 0;
  border-top: 1px solid var(--color-margin);
}

.doctrinal-browse__citations li {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.94rem;
  line-height: 1.5;
}

.doctrinal-browse__citations strong {
  color: var(--color-ink);
  font-weight: 650;
}

.doctrinal-browse__citations a {
  align-items: baseline;
  color: var(--color-lapis);
  display: inline-flex;
  gap: 0.3rem;
  text-decoration: none;
}

.doctrinal-browse__citations a:hover {
  text-decoration: underline;
  text-underline-offset: 0.2rem;
}

.doctrinal-browse__citations p {
  margin: 0.4rem 0 0;
}

.doctrinal-browse__empty {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-style: italic;
  line-height: 1.55;
  margin: 1.25rem 0 0;
}
</style>
