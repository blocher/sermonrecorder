import { Capacitor } from '@capacitor/core'
import { Uploader, type UploadEvent } from '@capgo/capacitor-uploader'
import { API_BASE_URL, authorizedAccessToken } from '../auth/useAuth'
import type { LocalDraft } from '../recording/draftRepository'
import { nativeDraftFileUri } from '../recording/nativeDraftFiles'
import { startUploadKeepAlive, stopUploadKeepAlive } from './uploadKeepAlive'

export interface UploadedSermon {
  id: string
  source_draft_id: string
  processing_status: 'uploaded' | 'processing' | 'ready' | 'failed'
}

type UploadProgress = (value: number) => void

const INTERRUPTED_UPLOAD_MESSAGE =
  'The upload was interrupted. Leave Pewcorder alone for a moment, then try Process again — your recording is still on this device.'

const ACTIVE_UPLOAD_DRAFT_KEY = 'pewcorder.activeUploadDraftId'

function metadata(draft: LocalDraft): Record<string, string> {
  const duration = Math.max(1, Math.round(Number(draft.durationSeconds) || 1))
  const fields: Record<string, string> = {
    source_draft_id: draft.id,
    captured_at: draft.createdAt,
    duration_seconds: String(duration),
  }
  if (
    draft.latitude != null &&
    draft.longitude != null &&
    Number.isFinite(draft.latitude) &&
    Number.isFinite(draft.longitude)
  ) {
    fields.capture_latitude = draft.latitude.toFixed(6)
    fields.capture_longitude = draft.longitude.toFixed(6)
  }
  return fields
}

function parseResponse(body: string | undefined): UploadedSermon {
  if (!body) throw new Error('The server accepted no Sermon details.')
  return JSON.parse(body) as UploadedSermon
}

function rememberActiveUpload(draftId: string): void {
  try {
    localStorage.setItem(ACTIVE_UPLOAD_DRAFT_KEY, draftId)
  } catch {
    // Ignore quota / private-mode failures.
  }
}

function forgetActiveUpload(draftId?: string): void {
  try {
    if (!draftId || localStorage.getItem(ACTIVE_UPLOAD_DRAFT_KEY) === draftId) {
      localStorage.removeItem(ACTIVE_UPLOAD_DRAFT_KEY)
    }
  } catch {
    // Ignore storage failures.
  }
}

export function getActiveUploadDraftId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_UPLOAD_DRAFT_KEY)
  } catch {
    return null
  }
}

/** Idempotent lookup: POST with source_draft_id returns the existing Sermon if already uploaded. */
export async function findUploadedSermonForDraft(
  sourceDraftId: string,
): Promise<UploadedSermon | null> {
  const token = await authorizedAccessToken()
  const query = new URLSearchParams({ source_draft_id: sourceDraftId }).toString()
  const response = await fetch(`${API_BASE_URL}/api/sermons/?${query}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 200 || response.status === 201) {
    return parseResponse(await response.text())
  }
  return null
}

async function uploadBrowserDraft(
  draft: LocalDraft,
  token: string,
  onProgress?: UploadProgress,
): Promise<UploadedSermon> {
  if (!draft.audio) throw new Error('The local Draft audio could not be opened.')

  const body = new FormData()
  for (const [key, value] of Object.entries(metadata(draft))) body.append(key, value)
  body.append('audio', draft.audio, draft.mimeType.includes('mp4') ? 'sermon.m4a' : 'sermon.webm')

  onProgress?.(0.05)
  const response = await fetch(`${API_BASE_URL}/api/sermons/`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body,
  })
  const responseBody = await response.text()
  if (!response.ok) {
    try {
      const details = JSON.parse(responseBody) as Record<string, string[]>
      throw new Error(Object.values(details).flat()[0] ?? 'Draft upload failed.')
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error('Draft upload failed.')
      throw error
    }
  }
  onProgress?.(1)
  return parseResponse(responseBody)
}

function normalizeNativeFailure(error: unknown, statusCode?: number): Error {
  if (typeof statusCode === 'number' && statusCode >= 400 && statusCode < 500) {
    return new Error('Draft upload failed.')
  }
  if (error instanceof Error && error.message.trim()) {
    const looksNetwork =
      /network|timeout|timed out|abort|cancel|connection|offline|lost|interrupted/i.test(
        error.message,
      )
    if (!looksNetwork) return error
  }
  return new Error(INTERRUPTED_UPLOAD_MESSAGE)
}

async function resolveAfterAccepted(draftId: string): Promise<UploadedSermon> {
  const first = await findUploadedSermonForDraft(draftId)
  if (first?.id) return first
  await new Promise((resolve) => setTimeout(resolve, 400))
  const second = await findUploadedSermonForDraft(draftId)
  if (second?.id) return second
  throw new Error('The server accepted no Sermon details.')
}

async function uploadNativeDraft(
  draft: LocalDraft,
  token: string,
  onProgress?: UploadProgress,
): Promise<UploadedSermon> {
  if (!draft.audioPath) throw new Error('The local Draft audio file could not be opened.')

  const existing = await findUploadedSermonForDraft(draft.id).catch(() => null)
  if (existing?.id) {
    onProgress?.(1)
    return existing
  }

  const meta = metadata(draft)
  rememberActiveUpload(draft.id)
  await startUploadKeepAlive()

  let uploadId = ''
  const pendingEvents: UploadEvent[] = []
  let listenerHandle: { remove: () => Promise<void> } | undefined

  try {
    let settle!: (result: PromiseSettledResult<UploadedSermon>) => void
    const outcome = new Promise<UploadedSermon>((resolve, reject) => {
      let settled = false
      settle = (result) => {
        if (settled) return
        settled = true
        if (result.status === 'fulfilled') resolve(result.value)
        else reject(result.reason)
      }
    })

    const handleEvent = async (event: UploadEvent): Promise<void> => {
      if (event.id !== uploadId) return

      if (event.name === 'uploading' && event.payload.percent != null) {
        onProgress?.(Math.min(1, Math.max(0, event.payload.percent / 100)))
        return
      }

      if (event.name !== 'completed' && event.name !== 'failed') return

      if (event.eventId) {
        await Uploader.acknowledgeEvent({ eventId: event.eventId }).catch(() => undefined)
      }

      const statusCode = event.payload.statusCode
      if (event.name === 'completed' && (statusCode === 200 || statusCode === 201)) {
        onProgress?.(1)
        try {
          settle({ status: 'fulfilled', value: await resolveAfterAccepted(draft.id) })
        } catch (error) {
          settle({ status: 'rejected', reason: normalizeNativeFailure(error, statusCode) })
        }
        return
      }

      const recovered = await findUploadedSermonForDraft(draft.id).catch(() => null)
      if (recovered?.id) {
        onProgress?.(1)
        settle({ status: 'fulfilled', value: recovered })
        return
      }

      settle({
        status: 'rejected',
        reason: normalizeNativeFailure(
          event.payload.error ? new Error(event.payload.error) : undefined,
          statusCode,
        ),
      })
    }

    listenerHandle = await Uploader.addListener('events', (event: UploadEvent) => {
      if (!uploadId) {
        pendingEvents.push(event)
        return
      }
      void handleEvent(event)
    })

    const filePath = await nativeDraftFileUri(draft.audioPath)
    const started = await Uploader.startUpload({
      filePath,
      serverUrl: `${API_BASE_URL}/api/sermons/`,
      method: 'POST',
      uploadType: 'multipart',
      fileField: 'audio',
      mimeType: draft.mimeType || 'audio/mp4',
      parameters: meta,
      headers: { Authorization: `Bearer ${token}` },
      notificationTitle: 'Uploading sermon',
      maxRetries: 2,
    })
    uploadId = started.id
    onProgress?.(0.02)
    for (const event of pendingEvents.splice(0)) void handleEvent(event)
    return await outcome
  } catch (error) {
    const recovered = await findUploadedSermonForDraft(draft.id).catch(() => null)
    if (recovered?.id) return recovered
    throw normalizeNativeFailure(error)
  } finally {
    forgetActiveUpload(draft.id)
    if (listenerHandle) await listenerHandle.remove().catch(() => undefined)
    await stopUploadKeepAlive()
  }
}

export async function uploadDraft(
  draft: LocalDraft,
  onProgress?: UploadProgress,
): Promise<UploadedSermon> {
  const token = await authorizedAccessToken()
  return Capacitor.isNativePlatform()
    ? uploadNativeDraft(draft, token, onProgress)
    : uploadBrowserDraft(draft, token, onProgress)
}
