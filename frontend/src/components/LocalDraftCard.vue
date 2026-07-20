<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CloudUpload, Pause, Play, Trash2 } from '@lucide/vue'
import type { LocalDraft } from '../recording/draftRepository'

const props = defineProps<{
  draft: LocalDraft
}>()

const emit = defineEmits<{
  delete: [id: string]
  upload: [id: string]
}>()

const audio = ref<HTMLAudioElement>()
const audioUrl = ref('')
const playing = ref(false)
const confirmingDelete = ref(false)
const playbackError = ref(false)

const title = computed(() => {
  const date = new Date(props.draft.createdAt)
  const formatted = new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(date)
  return `${formatted} draft`
})

const time = computed(() => {
  const date = new Date(props.draft.createdAt)
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
})

const duration = computed(() => {
  const minutes = Math.floor(props.draft.durationSeconds / 60)
  const seconds = props.draft.durationSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

const size = computed(() => `${(props.draft.sizeBytes / 1_048_576).toFixed(1)} MB`)

function setAudioUrl(): void {
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  audioUrl.value = URL.createObjectURL(props.draft.audio)
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
    playing.value = false
    playbackError.value = true
  }
}

function deleteDraft(): void {
  confirmingDelete.value = false
  emit('delete', props.draft.id)
}

watch(() => props.draft.audio, setAudioUrl, { immediate: true })

onBeforeUnmount(() => {
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
})
</script>

<template>
  <article class="local-draft">
    <audio
      ref="audio"
      :src="audioUrl"
      @play="playing = true"
      @pause="playing = false"
      @ended="playing = false"
    ></audio>

    <button
      class="local-draft__play"
      type="button"
      :aria-label="playing ? `Pause ${title}` : `Play ${title}`"
      @click="togglePlayback"
    >
      <Pause v-if="playing" :size="18" fill="currentColor" aria-hidden="true" />
      <Play v-else :size="18" fill="currentColor" aria-hidden="true" />
    </button>

    <div class="local-draft__body">
      <span class="local-draft__eyebrow">On this device</span>
      <strong>{{ title }}</strong>
      <small>{{ time }} · {{ duration }} · {{ size }}</small>
      <small v-if="playbackError" class="local-draft__error">Audio playback failed on this device.</small>
    </div>

    <div v-if="!confirmingDelete" class="local-draft__actions">
      <button class="local-draft__upload" type="button" @click="emit('upload', draft.id)">
        <CloudUpload :size="16" aria-hidden="true" />
        Upload
      </button>
      <button
        class="local-draft__delete"
        type="button"
        :aria-label="`Delete ${title}`"
        @click="confirmingDelete = true"
      >
        <Trash2 :size="16" aria-hidden="true" />
      </button>
    </div>

    <div v-else class="local-draft__confirm">
      <span>Delete this Draft?</span>
      <button type="button" @click="confirmingDelete = false">Keep</button>
      <button type="button" @click="deleteDraft">Delete</button>
    </div>
  </article>
</template>

<style scoped>
.local-draft {
  align-items: center;
  background: var(--color-margin);
  border-left: 2px solid var(--color-lapis);
  display: grid;
  gap: 0.9rem;
  grid-template-columns: auto 1fr auto;
  padding: 1rem 1.1rem;
}

.local-draft + .local-draft {
  border-top: 1px solid var(--color-vellum);
}

.local-draft__play {
  align-items: center;
  background: var(--color-vellum);
  border: 1px solid rgba(47, 75, 124, 0.35);
  border-radius: 50%;
  color: var(--color-lapis);
  cursor: pointer;
  display: flex;
  height: 2.7rem;
  justify-content: center;
  padding-left: 0.1rem;
  width: 2.7rem;
}

.local-draft__eyebrow,
.local-draft strong,
.local-draft small {
  display: block;
  font-family: var(--font-utility);
}

.local-draft .local-draft__error {
  color: var(--color-rubric);
}

.local-draft__eyebrow {
  color: var(--color-rubric);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  margin-bottom: 0.15rem;
  text-transform: uppercase;
}

.local-draft strong {
  font-size: 0.9rem;
  font-weight: 650;
}

.local-draft small {
  color: var(--color-ink-muted);
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.local-draft__actions,
.local-draft__confirm {
  align-items: center;
  display: flex;
  gap: 0.35rem;
}

.local-draft__actions button,
.local-draft__confirm button {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.75rem;
  font-weight: 700;
  gap: 0.35rem;
  min-height: 2.5rem;
  padding: 0.5rem;
}

.local-draft__delete {
  color: var(--color-rubric) !important;
}

.local-draft__confirm {
  flex-wrap: wrap;
  justify-content: end;
}

.local-draft__confirm span {
  color: var(--color-rubric);
  flex-basis: 100%;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 650;
  text-align: right;
}

.local-draft__confirm button:last-child {
  color: var(--color-rubric);
}

@media (max-width: 640px) {
  .local-draft {
    grid-template-columns: auto 1fr;
  }

  .local-draft__actions,
  .local-draft__confirm {
    grid-column: 2;
    justify-content: start;
  }

  .local-draft__confirm span {
    text-align: left;
  }
}
</style>
