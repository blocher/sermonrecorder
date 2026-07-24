<script setup lang="ts">
import { nextTick, ref } from 'vue'
import {
  ownerSermonSections,
  sharedSermonSections,
  type SermonSection,
} from '../sermons/sections'

const props = withDefaults(
  defineProps<{
    activeSection: SermonSection
    includeReflection?: boolean
  }>(),
  {
    includeReflection: false,
  },
)

const emit = defineEmits<{
  select: [section: SermonSection]
}>()

const tabs = ref<HTMLElement>()
const tabButtons = ref<HTMLButtonElement[]>([])
const sections = props.includeReflection ? ownerSermonSections : sharedSermonSections

function scrollIntoView(options?: ScrollIntoViewOptions): void {
  tabs.value?.scrollIntoView(options)
}

async function moveFocus(event: KeyboardEvent, index: number): Promise<void> {
  let nextIndex: number
  if (event.key === 'ArrowRight') nextIndex = (index + 1) % sections.length
  else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + sections.length) % sections.length
  else if (event.key === 'Home') nextIndex = 0
  else if (event.key === 'End') nextIndex = sections.length - 1
  else return

  event.preventDefault()
  const nextSection = sections[nextIndex]?.[0]
  if (!nextSection) return
  emit('select', nextSection)
  await nextTick()
  tabButtons.value[nextIndex]?.focus()
}

defineExpose({ scrollIntoView })
</script>

<template>
  <nav ref="tabs" class="section-tabs" aria-label="Sermon sections" role="tablist">
    <button
      v-for="[section, label] in sections"
      :id="`sermon-tab-${section}`"
      ref="tabButtons"
      :key="section"
      type="button"
      role="tab"
      :class="{ active: activeSection === section }"
      :aria-selected="activeSection === section"
      :aria-controls="`sermon-panel-${section}`"
      :tabindex="activeSection === section ? 0 : -1"
      @click="emit('select', section)"
      @keydown="moveFocus($event, sections.findIndex(([candidate]) => candidate === section))"
    >
      {{ label }}
    </button>
  </nav>
</template>

<style scoped>
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

.section-tabs button:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: -4px;
}

@media (max-width: 600px) {
  .section-tabs {
    margin-inline: -0.4rem;
  }

  .section-tabs button {
    font-size: 0.72rem;
  }
}
</style>
