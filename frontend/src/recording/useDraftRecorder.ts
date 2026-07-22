import { App } from '@capacitor/app'
import { Capacitor } from '@capacitor/core'
import { computed, ref, shallowRef } from 'vue'
import { captureRecordingLocation } from '../location/captureRecordingLocation'
import { createAudioRecorder, supportsAudioRecording } from './audioRecorder'
import {
  createDraft,
  deleteDraft,
  listDrafts,
  updateDraft,
  type DraftAudioInput,
  type LocalDraft,
  type LocalDraftMetadataPatch,
} from './draftRepository'

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'saving' | 'error'

const recorder = createAudioRecorder()
const state = ref<RecorderState>('idle')
const elapsedSeconds = ref(0)
const drafts = ref<LocalDraft[]>([])
const errorMessage = ref('')
const lastSavedDraft = ref<LocalDraft>()
const wizardDraftId = ref<string>()
const initialized = ref(false)
let elapsedTimer: number | undefined
let startedAt = 0
let lifecycleListenerInstalled = false
const pendingRecording = shallowRef<{ audio: DraftAudioInput; durationSeconds: number }>()

function stopElapsedTimer(): void {
  if (elapsedTimer) window.clearInterval(elapsedTimer)
  elapsedTimer = undefined
}

function startElapsedTimer(): void {
  stopElapsedTimer()
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1_000)
  }, 250)
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

async function captureLocationForDraft(draftId: string): Promise<LocalDraft | undefined> {
  const result = await captureRecordingLocation()
  try {
    const patch: LocalDraftMetadataPatch =
      result.status === 'captured'
        ? {
            locationStatus: 'captured',
            latitude: result.latitude,
            longitude: result.longitude,
          }
        : { locationStatus: result.status }

    const updated = await updateDraft(draftId, patch)
    drafts.value = drafts.value.map((draft) => (draft.id === draftId ? updated : draft))
    if (lastSavedDraft.value?.id === draftId) lastSavedDraft.value = updated
    return updated
  } catch {
    // Location enrichment must never jeopardize a saved Draft.
    return undefined
  }
}

async function initialize(): Promise<void> {
  if (initialized.value) return

  try {
    await refreshDrafts()

    if (Capacitor.isNativePlatform()) {
      if (await recorder.isActive()) {
        elapsedSeconds.value = 0
        startedAt = performance.now()
        state.value = 'recording'
        startElapsedTimer()
      }

      if (!lifecycleListenerInstalled) {
        await App.addListener('resume', () => {
          void reconcileNativeRecording()
        })
        lifecycleListenerInstalled = true
      }
    }

    initialized.value = true
  } catch (error) {
    state.value = 'error'
    errorMessage.value = recordingError(error)
  }
}

async function reconcileNativeRecording(): Promise<void> {
  if (!Capacitor.isNativePlatform() || state.value !== 'recording') return

  try {
    if (await recorder.isActive()) return
  } catch {
    return
  }

  stopElapsedTimer()
  state.value = 'error'
  errorMessage.value =
    'Recording stopped while Pewcorder was in the background. Any audio returned by the device could not be recovered.'
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
    startElapsedTimer()
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
    const draft = await createDraft(
      pendingRecording.value.audio,
      pendingRecording.value.durationSeconds,
    )
    pendingRecording.value = undefined
    lastSavedDraft.value = draft
    drafts.value = [draft, ...drafts.value.filter((item) => item.id !== draft.id)]
    wizardDraftId.value = draft.id
    state.value = 'idle'
    // Capture place before refreshing the list so a concurrent IDB read cannot
    // overwrite an in-memory "captured" status with a stale "pending" row.
    void captureLocationForDraft(draft.id).then(() => refreshDrafts())
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
    const capture = await recorder.stop()
    pendingRecording.value = {
      audio: capture.audio,
      durationSeconds: Math.max(durationSeconds, capture.durationSeconds ?? 0),
    }
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

async function patchDraft(id: string, patch: LocalDraftMetadataPatch): Promise<LocalDraft> {
  const updated = await updateDraft(id, patch)
  drafts.value = drafts.value.map((draft) => (draft.id === id ? updated : draft))
  if (lastSavedDraft.value?.id === id) lastSavedDraft.value = updated
  return updated
}

function openDraftWizard(id: string): void {
  wizardDraftId.value = id
}

function closeDraftWizard(): void {
  wizardDraftId.value = undefined
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
    wizardDraftId,
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
    patchDraft,
    openDraftWizard,
    closeDraftWizard,
    refreshDrafts,
    captureLocationForDraft,
    clearError,
  }
}
