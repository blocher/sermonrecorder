import { computed, ref, shallowRef } from 'vue'
import { BrowserAudioRecorder, supportsAudioRecording } from './browserAudioRecorder'
import {
  createDraft,
  deleteDraft,
  listDrafts,
  type LocalDraft,
} from './draftRepository'

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'saving' | 'error'

const recorder = new BrowserAudioRecorder()
const state = ref<RecorderState>('idle')
const elapsedSeconds = ref(0)
const drafts = ref<LocalDraft[]>([])
const errorMessage = ref('')
const lastSavedDraft = ref<LocalDraft>()
const initialized = ref(false)
let elapsedTimer: number | undefined
let startedAt = 0
const pendingRecording = shallowRef<{ audio: Blob; durationSeconds: number }>()

function stopElapsedTimer(): void {
  if (elapsedTimer) window.clearInterval(elapsedTimer)
  elapsedTimer = undefined
}

function recordingError(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
      return 'Microphone access is off. Allow it in device settings, then try again.'
    }

    if (error.name === 'NotFoundError') {
      return 'No microphone was found on this device.'
    }

    if (error.name === 'NotReadableError') {
      return 'The microphone is being used by another app. Close it, then try again.'
    }
  }

  return error instanceof Error ? error.message : 'Recording could not start. Try again.'
}

async function refreshDrafts(): Promise<void> {
  drafts.value = await listDrafts()
}

async function initialize(): Promise<void> {
  if (initialized.value) return

  try {
    await refreshDrafts()
    initialized.value = true
  } catch (error) {
    state.value = 'error'
    errorMessage.value = recordingError(error)
  }
}

async function start(): Promise<void> {
  if (state.value === 'requesting' || state.value === 'saving' || state.value === 'recording') return
  if (pendingRecording.value) {
    await savePendingRecording()
    return
  }

  errorMessage.value = ''
  lastSavedDraft.value = undefined
  elapsedSeconds.value = 0
  state.value = 'requesting'

  try {
    await recorder.start()
    startedAt = performance.now()
    state.value = 'recording'
    elapsedTimer = window.setInterval(() => {
      elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1_000)
    }, 250)
  } catch (error) {
    state.value = 'error'
    errorMessage.value = recordingError(error)
  }
}

async function savePendingRecording(): Promise<void> {
  if (!pendingRecording.value) return

  state.value = 'saving'
  errorMessage.value = ''

  try {
    lastSavedDraft.value = await createDraft(
      pendingRecording.value.audio,
      pendingRecording.value.durationSeconds,
    )
    pendingRecording.value = undefined
    await refreshDrafts()
    state.value = 'idle'
  } catch (error) {
    state.value = 'error'
    errorMessage.value = `${recordingError(error)} The audio is still open; choose “Try saving again.”`
  }
}

async function stop(): Promise<void> {
  if (state.value !== 'recording') return

  stopElapsedTimer()
  const durationSeconds = Math.max(
    1,
    elapsedSeconds.value,
    Math.round((performance.now() - startedAt) / 1_000),
  )
  state.value = 'saving'

  try {
    const audio = await recorder.stop()
    pendingRecording.value = { audio, durationSeconds }
    await savePendingRecording()
  } catch (error) {
    state.value = 'error'
    errorMessage.value = recordingError(error)
  }
}

async function toggle(): Promise<void> {
  if (state.value === 'recording') {
    await stop()
  } else {
    await start()
  }
}

async function removeDraft(id: string): Promise<void> {
  await deleteDraft(id)
  await refreshDrafts()
}

function clearError(): void {
  errorMessage.value = ''
  state.value = 'idle'
}

export function useDraftRecorder() {
  return {
    state,
    elapsedSeconds,
    drafts,
    errorMessage,
    lastSavedDraft,
    isSupported: computed(() => supportsAudioRecording()),
    hasPendingRecording: computed(() => Boolean(pendingRecording.value)),
    isRecording: computed(() => state.value === 'recording'),
    isBusy: computed(() => state.value === 'requesting' || state.value === 'saving'),
    initialize,
    start,
    stop,
    toggle,
    retrySave: savePendingRecording,
    removeDraft,
    clearError,
  }
}
