import { FileTransfer } from '@capacitor/file-transfer'
import { Capacitor } from '@capacitor/core'
import { API_BASE_URL, authorizedAccessToken } from '../auth/useAuth'
import type { LocalDraft } from '../recording/draftRepository'
import { nativeDraftFileUri } from '../recording/nativeDraftFiles'

export interface UploadedSermon {
  id: string
  source_draft_id: string
  processing_status: 'uploaded' | 'processing' | 'ready' | 'failed'
}

type UploadProgress = (value: number) => void

function metadata(draft: LocalDraft): Record<string, string> {
  const duration = Math.max(1, Math.round(Number(draft.durationSeconds) || 1))
  return {
    source_draft_id: draft.id,
    captured_at: draft.createdAt,
    duration_seconds: String(duration),
  }
}

function parseResponse(body: string | undefined): UploadedSermon {
  if (!body) throw new Error('The server accepted no Sermon details.')
  return JSON.parse(body) as UploadedSermon
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

async function uploadNativeDraft(
  draft: LocalDraft,
  token: string,
  onProgress?: UploadProgress,
): Promise<UploadedSermon> {
  if (!draft.audioPath) throw new Error('The local Draft audio file could not be opened.')

  const meta = metadata(draft)
  const query = new URLSearchParams(meta).toString()
  const url = `${API_BASE_URL}/api/sermons/?${query}`
  const listener = await FileTransfer.addListener('progress', (event) => {
    if (event.type !== 'upload' || event.url !== url || !event.lengthComputable) return
    onProgress?.(Math.min(1, event.bytes / event.contentLength))
  })

  try {
    const result = await FileTransfer.uploadFile({
      url,
      path: await nativeDraftFileUri(draft.audioPath),
      method: 'POST',
      fileKey: 'audio',
      mimeType: draft.mimeType || 'audio/mp4',
      params: meta,
      headers: { Authorization: `Bearer ${token}` },
      chunkedMode: false,
      progress: true,
      connectTimeout: 30_000,
      readTimeout: 10 * 60_000,
    })
    onProgress?.(1)
    return parseResponse(result.response)
  } catch (error: unknown) {
    const transferError = error as { data?: { body?: string }; body?: string; response?: string }
    const responseBody = transferError?.data?.body ?? transferError?.body ?? transferError?.response
    if (responseBody && typeof responseBody === 'string') {
      try {
        const details = JSON.parse(responseBody) as Record<string, unknown>
        const firstMessage = Object.values(details).flat()[0]
        if (typeof firstMessage === 'string' && firstMessage) throw new Error(firstMessage)
      } catch (parseError) {
        if (!(parseError instanceof SyntaxError)) throw parseError
      }
    }
    throw error
  } finally {
    await listener.remove()
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
