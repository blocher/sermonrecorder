<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  Bold,
  Heading2,
  Italic,
  List,
  ListOrdered,
  Maximize2,
  Minimize2,
  Quote,
} from '@lucide/vue'

const props = defineProps<{
  modelValue: string
  prompt: string
  saving?: boolean
  message?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  save: []
}>()

const expanded = ref(false)
const expandButton = ref<HTMLButtonElement>()
const inlineEditor = ref<HTMLTextAreaElement>()
const fullEditor = ref<HTMLTextAreaElement>()
const wordCount = computed(() => {
  const text = props.modelValue.trim()
  return text ? text.split(/\s+/).length : 0
})

function editor(): HTMLTextAreaElement | undefined {
  return expanded.value ? fullEditor.value : inlineEditor.value
}

function updateValue(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}

async function replaceSelection(
  replacement: (selected: string) => string,
  fallback: string,
): Promise<void> {
  const element = editor()
  if (!element) return
  const start = element.selectionStart
  const end = element.selectionEnd
  const selected = props.modelValue.slice(start, end)
  const inserted = replacement(selected || fallback)
  emit(
    'update:modelValue',
    `${props.modelValue.slice(0, start)}${inserted}${props.modelValue.slice(end)}`,
  )
  await nextTick()
  const nextEditor = editor()
  nextEditor?.focus()
  nextEditor?.setSelectionRange(start, start + inserted.length)
}

function wrap(prefix: string, suffix: string, fallback: string): void {
  void replaceSelection((selected) => `${prefix}${selected}${suffix}`, fallback)
}

function prefixLines(prefix: string, fallback: string, numbered = false): void {
  void replaceSelection(
    (selected) =>
      selected
        .split('\n')
        .map((line, index) => `${numbered ? `${index + 1}. ` : prefix}${line}`)
        .join('\n'),
    fallback,
  )
}

async function openExpanded(): Promise<void> {
  expanded.value = true
  await nextTick()
  fullEditor.value?.focus()
}

async function closeExpanded(): Promise<void> {
  expanded.value = false
  await nextTick()
  expandButton.value?.focus()
}

function setBackgroundInert(inert: boolean): void {
  for (const selector of ['.app-header', '.app-content', '.record-control']) {
    const element = document.querySelector<HTMLElement>(selector)
    element?.toggleAttribute('inert', inert)
    if (inert) element?.setAttribute('aria-hidden', 'true')
    else element?.removeAttribute('aria-hidden')
  }
}

watch(expanded, (open) => {
  document.body.classList.toggle('reflection-editor-lock', open)
  setBackgroundInert(open)
})

onBeforeUnmount(() => {
  document.body.classList.remove('reflection-editor-lock')
  setBackgroundInert(false)
})
</script>

<template>
  <div class="reflection-editor">
    <div class="reflection-editor__toolbar" role="toolbar" aria-label="Reflection formatting">
      <button type="button" title="Heading" aria-label="Heading" @click="prefixLines('## ', 'Heading')">
        <Heading2 :size="17" aria-hidden="true" />
      </button>
      <button type="button" title="Bold" aria-label="Bold" @click="wrap('**', '**', 'important words')">
        <Bold :size="17" aria-hidden="true" />
      </button>
      <button type="button" title="Italic" aria-label="Italic" @click="wrap('_', '_', 'emphasis')">
        <Italic :size="17" aria-hidden="true" />
      </button>
      <button
        type="button"
        title="Bulleted list"
        aria-label="Bulleted list"
        @click="prefixLines('- ', 'List item')"
      >
        <List :size="17" aria-hidden="true" />
      </button>
      <button
        type="button"
        title="Numbered list"
        aria-label="Numbered list"
        @click="prefixLines('', 'List item', true)"
      >
        <ListOrdered :size="17" aria-hidden="true" />
      </button>
      <button type="button" title="Quote" aria-label="Quote" @click="prefixLines('> ', 'Quote')">
        <Quote :size="17" aria-hidden="true" />
      </button>
      <span class="reflection-editor__toolbar-spacer"></span>
      <button
        ref="expandButton"
        type="button"
        title="Open full screen"
        aria-label="Open full-screen editor"
        @click="openExpanded"
      >
        <Maximize2 :size="17" aria-hidden="true" />
        <span>Full screen</span>
      </button>
    </div>
    <textarea
      ref="inlineEditor"
      :value="modelValue"
      rows="10"
      aria-label="Your private Reflection"
      placeholder="Begin writing…"
      @input="updateValue"
    ></textarea>
    <div class="reflection-editor__footer">
      <span>{{ message || `Only you can see this Reflection · ${wordCount} words` }}</span>
      <button type="button" :disabled="saving || !modelValue.trim()" @click="emit('save')">
        {{ saving ? 'Saving…' : 'Save Reflection' }}
      </button>
    </div>
  </div>

  <Teleport to="body">
    <div
      v-if="expanded"
      class="reflection-writing-room"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reflection-writing-room-title"
      aria-describedby="reflection-writing-room-prompt"
      @keydown.esc="closeExpanded"
    >
      <header class="reflection-writing-room__header">
        <div>
          <p class="rubric-label">Private writing room</p>
          <h2 id="reflection-writing-room-title">Reflection</h2>
        </div>
        <button type="button" aria-label="Close full-screen editor" @click="closeExpanded">
          <Minimize2 :size="18" aria-hidden="true" />
          Close
        </button>
      </header>
      <div class="reflection-writing-room__body">
        <p id="reflection-writing-room-prompt" class="reflection-writing-room__prompt">
          {{ prompt }}
        </p>
        <div class="reflection-editor__toolbar" role="toolbar" aria-label="Reflection formatting">
          <button type="button" title="Heading" aria-label="Heading" @click="prefixLines('## ', 'Heading')">
            <Heading2 :size="18" aria-hidden="true" />
          </button>
          <button type="button" title="Bold" aria-label="Bold" @click="wrap('**', '**', 'important words')">
            <Bold :size="18" aria-hidden="true" />
          </button>
          <button type="button" title="Italic" aria-label="Italic" @click="wrap('_', '_', 'emphasis')">
            <Italic :size="18" aria-hidden="true" />
          </button>
          <button type="button" title="Bulleted list" aria-label="Bulleted list" @click="prefixLines('- ', 'List item')">
            <List :size="18" aria-hidden="true" />
          </button>
          <button
            type="button"
            title="Numbered list"
            aria-label="Numbered list"
            @click="prefixLines('', 'List item', true)"
          >
            <ListOrdered :size="18" aria-hidden="true" />
          </button>
          <button type="button" title="Quote" aria-label="Quote" @click="prefixLines('> ', 'Quote')">
            <Quote :size="18" aria-hidden="true" />
          </button>
        </div>
        <textarea
          ref="fullEditor"
          :value="modelValue"
          aria-label="Your private Reflection"
          placeholder="Begin writing…"
          @input="updateValue"
        ></textarea>
        <footer class="reflection-writing-room__footer">
          <span>{{ message || `${wordCount} words · saved only to your private journal` }}</span>
          <button type="button" :disabled="saving || !modelValue.trim()" @click="emit('save')">
            {{ saving ? 'Saving…' : 'Save Reflection' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
:global(body.reflection-editor-lock) {
  overflow: hidden;
}

.reflection-editor {
  border: 1px solid var(--color-margin);
  margin-top: 1.25rem;
}

.reflection-editor__toolbar {
  align-items: center;
  background: color-mix(in srgb, var(--color-margin) 52%, var(--color-vellum-light));
  border-bottom: 1px solid var(--color-margin);
  display: flex;
  flex-wrap: wrap;
  gap: 0.15rem;
  padding: 0.35rem;
}

.reflection-editor__toolbar button {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-ink-muted);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 700;
  gap: 0.35rem;
  min-height: 2.25rem;
  padding: 0.4rem 0.55rem;
}

.reflection-editor__toolbar button:hover,
.reflection-editor__toolbar button:focus-visible {
  background: var(--color-vellum-light);
  color: var(--color-lapis);
}

.reflection-editor__toolbar-spacer {
  flex: 1;
}

.reflection-editor > textarea,
.reflection-writing-room textarea {
  background: var(--color-vellum-light);
  border: 0;
  color: var(--color-ink);
  display: block;
  font-family: var(--font-reading);
  font-size: 1.04rem;
  line-height: 1.75;
  padding: 1.1rem;
  resize: vertical;
  width: 100%;
}

.reflection-editor > textarea:focus,
.reflection-writing-room textarea:focus {
  outline: 2px solid color-mix(in srgb, var(--color-lapis) 45%, transparent);
  outline-offset: -2px;
}

.reflection-editor__footer,
.reflection-writing-room__footer {
  align-items: center;
  border-top: 1px solid var(--color-margin);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.65rem 0.75rem;
}

.reflection-editor__footer span,
.reflection-writing-room__footer span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.74rem;
}

.reflection-editor__footer button,
.reflection-writing-room__footer button {
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  min-height: 2.5rem;
  padding: 0.55rem 0.85rem;
}

.reflection-editor__footer button:disabled,
.reflection-writing-room__footer button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.reflection-writing-room {
  background: var(--color-vellum);
  display: flex;
  flex-direction: column;
  inset: 0;
  padding: max(1rem, env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right))
    max(1rem, env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left));
  position: fixed;
  z-index: 100;
}

.reflection-writing-room__header {
  align-items: center;
  border-bottom: 1px solid var(--color-rule-gold);
  display: flex;
  justify-content: space-between;
  margin: 0 auto;
  max-width: 64rem;
  padding: 0.5rem 0 1rem;
  width: 100%;
}

.reflection-writing-room__header h2 {
  font-family: var(--font-display);
  font-size: clamp(2rem, 5vw, 3.25rem);
  font-weight: 540;
  letter-spacing: -0.045em;
  margin: 0.2rem 0 0;
}

.reflection-writing-room__header > button {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
  gap: 0.4rem;
  min-height: 2.6rem;
  padding: 0.5rem 0.75rem;
}

.reflection-writing-room__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  margin: 0 auto;
  max-width: 64rem;
  min-height: 0;
  padding-top: 1rem;
  width: 100%;
}

.reflection-writing-room__prompt {
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: clamp(1.1rem, 2vw, 1.35rem);
  font-style: italic;
  margin: 0 0 1rem;
}

.reflection-writing-room textarea {
  flex: 1;
  min-height: 12rem;
  resize: none;
}

@media (max-width: 600px) {
  .reflection-editor__toolbar button span,
  .reflection-editor__footer span {
    display: none;
  }

  .reflection-editor__footer {
    justify-content: flex-end;
  }

  .reflection-writing-room__footer {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
