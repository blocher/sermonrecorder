<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  CircleAlert,
  CloudUpload,
  LoaderCircle,
  Pause,
  Play,
  RotateCcw,
  Trash2,
} from '@lucide/vue'
import type { ServerSermon } from '../sermons/serverSermon'

const props = defineProps<{
  sermon: ServerSermon
  retrying?: boolean
  deleting?: boolean
}>()

const emit = defineEmits<{
  retry: [id: string]
  delete: [id: string]
}>()

const audio = ref<HTMLAudioElement>()
const playbackUrl = ref(props.sermon.audio_url)
const playing = ref(false)
const playbackError = ref(false)
const confirmingDelete = ref(false)

const title = computed(() => {
  const captured = new Date(props.sermon.captured_at)
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(captured)
})

const details = computed(() => {
  const captured = new Date(props.sermon.captured_at)
  const time = new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(captured)
  const minutes = Math.max(1, Math.round(props.sermon.duration_seconds / 60))
  return `${time} · ${minutes} min`
})

const statusLabel = computed(() => {
  if (props.sermon.processing_status === 'processing') return 'Preparing'
  if (props.sermon.processing_status === 'failed') return 'Needs attention'
  return 'Safely uploaded'
})

const busy = computed(() => Boolean(props.retrying || props.deleting))

function syncPlaybackUrl(url: string): void {
  if (playing.value) return
  if (playbackUrl.value === url) return
  playbackUrl.value = url
  playbackError.value = false
}

async function waitForCanPlay(element: HTMLAudioElement): Promise<void> {
  if (element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return

  await new Promise<void>((resolve, reject) => {
    const onReady = () => {
      cleanup()
      resolve()
    }
    const onError = () => {
      cleanup()
      reject(new Error('This recording could not be loaded.'))
    }
    const cleanup = () => {
      element.removeEventListener('canplay', onReady)
      element.removeEventListener('error', onError)
    }
    element.addEventListener('canplay', onReady, { once: true })
    element.addEventListener('error', onError, { once: true })
    element.load()
  })
}

async function togglePlayback(): Promise<void> {
  const element = audio.value
  if (!element || !playbackUrl.value) {
    playbackError.value = true
    return
  }

  playbackError.value = false

  if (playing.value) {
    element.pause()
    return
  }

  try {
    await waitForCanPlay(element)
    await element.play()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    playing.value = false
    playbackError.value = true
  }
}

function confirmDelete(): void {
  confirmingDelete.value = false
  audio.value?.pause()
  emit('delete', props.sermon.id)
}

watch(
  () => props.sermon.audio_url,
  (url) => syncPlaybackUrl(url),
  { immediate: true },
)

watch(playing, (isPlaying) => {
  if (!isPlaying) syncPlaybackUrl(props.sermon.audio_url)
})

onBeforeUnmount(() => {
  audio.value?.pause()
})
</script>

<template>
  <article class="server-sermon" :class="`server-sermon--${sermon.processing_status}`">
    <button
      class="server-sermon__play"
      type="button"
      :aria-label="playing ? 'Pause recording' : 'Play recording'"
      :disabled="!playbackUrl || busy"
      @click="togglePlayback"
    >
      <Pause v-if="playing" :size="18" />
      <Play v-else :size="18" />
    </button>
    <div class="server-sermon__body">
      <span class="server-sermon__status">
        <LoaderCircle
          v-if="sermon.processing_status === 'processing' || busy"
          class="server-sermon__spinner"
          :size="12"
          aria-hidden="true"
        />
        {{ statusLabel }}
      </span>
      <strong>{{ title }} sermon</strong>
      <small>{{ details }}</small>
      <p :class="{ 'server-sermon__error': playbackError }">
        {{
          playbackError
            ? 'This recording could not be played. Delete it and record again after refreshing.'
            : sermon.processing_message
        }}
      </p>
      <div v-if="!confirmingDelete" class="server-sermon__actions">
        <button
          v-if="sermon.processing_status === 'failed'"
          type="button"
          :disabled="busy"
          @click="emit('retry', sermon.id)"
        >
          <RotateCcw :size="15" aria-hidden="true" />
          {{ retrying ? 'Retrying…' : 'Try again' }}
        </button>
        <button
          class="server-sermon__delete"
          type="button"
          :aria-label="`Delete ${title} sermon`"
          :disabled="busy"
          @click="confirmingDelete = true"
        >
          <Trash2 :size="15" aria-hidden="true" />
          {{ deleting ? 'Deleting…' : 'Delete' }}
        </button>
      </div>
      <div v-else class="server-sermon__confirm">
        <span>Delete this Sermon?</span>
        <button type="button" :disabled="busy" @click="confirmingDelete = false">Keep</button>
        <button type="button" :disabled="busy" @click="confirmDelete">Delete</button>
      </div>
    </div>
    <span
      v-if="sermon.processing_status === 'failed'"
      class="server-sermon__badge"
      aria-hidden="true"
    >
      <CircleAlert :size="16" />
    </span>
    <span
      v-else-if="sermon.processing_status === 'uploaded'"
      class="server-sermon__badge"
      aria-hidden="true"
    >
      <CloudUpload :size="16" />
    </span>
    <audio
      v-if="playbackUrl"
      ref="audio"
      preload="metadata"
      :src="playbackUrl"
      @play="playing = true"
      @pause="playing = false"
      @ended="playing = false"
      @error="playbackError = true"
    />
  </article>
</template>

<style scoped>
.server-sermon {
  align-items: start;
  background: color-mix(in srgb, var(--color-margin) 72%, var(--color-vellum-light));
  border-left: 2px solid var(--color-lapis);
  display: grid;
  gap: 0.9rem;
  grid-template-columns: auto 1fr auto;
  padding: 1rem 1.1rem;
}

.server-sermon + .server-sermon {
  border-top: 1px solid var(--color-vellum);
}

.server-sermon--failed {
  border-left-color: var(--color-rubric);
}

.server-sermon__play {
  align-items: center;
  background: var(--color-vellum);
  border: 1px solid color-mix(in srgb, var(--color-lapis) 35%, transparent);
  border-radius: 50%;
  color: var(--color-lapis);
  cursor: pointer;
  display: flex;
  height: 2.65rem;
  justify-content: center;
  padding-left: 0.1rem;
  width: 2.65rem;
}

.server-sermon__play:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.server-sermon--failed .server-sermon__play,
.server-sermon--failed .server-sermon__status,
.server-sermon--failed .server-sermon__badge {
  color: var(--color-rubric);
}

.server-sermon--failed .server-sermon__play {
  border-color: color-mix(in srgb, var(--color-rubric) 35%, transparent);
}

.server-sermon__badge {
  color: var(--color-lapis);
  margin-top: 0.45rem;
}

.server-sermon__status,
.server-sermon strong,
.server-sermon small {
  display: block;
  font-family: var(--font-utility);
}

.server-sermon__status {
  align-items: center;
  color: var(--color-lapis);
  display: inline-flex;
  font-size: 0.62rem;
  font-weight: 700;
  gap: 0.35rem;
  letter-spacing: 0.09em;
  margin-bottom: 0.15rem;
  text-transform: uppercase;
}

.server-sermon strong {
  font-size: 0.9rem;
  font-weight: 650;
}

.server-sermon small,
.server-sermon p {
  color: var(--color-ink-muted);
}

.server-sermon small {
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.server-sermon p {
  font-family: var(--font-reading);
  font-size: 0.78rem;
  line-height: 1.45;
  margin: 0.45rem 0 0;
}

.server-sermon__error {
  color: var(--color-rubric);
}

.server-sermon__actions,
.server-sermon__confirm {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.55rem;
}

.server-sermon__confirm span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.75rem;
  margin-right: 0.25rem;
}

.server-sermon__actions button,
.server-sermon__confirm button {
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
  min-height: 2.25rem;
  padding: 0.35rem 0.15rem;
}

.server-sermon__delete {
  color: var(--color-rubric) !important;
}

.server-sermon__actions button:disabled,
.server-sermon__confirm button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.server-sermon__spinner {
  animation: server-spin 1s linear infinite;
}

@keyframes server-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .server-sermon__spinner {
    animation: none;
  }
}
</style>
