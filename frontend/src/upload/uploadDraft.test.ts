import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  authorizedAccessToken: vi.fn(async () => 'access-token'),
  fetch: vi.fn(),
  native: { value: false },
  removeListener: vi.fn(async () => undefined),
  acknowledgeEvent: vi.fn(async () => undefined),
  addListener: vi.fn(),
  startUpload: vi.fn(),
  startUploadKeepAlive: vi.fn(async () => undefined),
  stopUploadKeepAlive: vi.fn(async () => undefined),
  eventHandler: null as null | ((event: unknown) => void),
}))

vi.mock('../auth/useAuth', () => ({
  API_BASE_URL: 'http://api.example.test',
  authorizedAccessToken: mocks.authorizedAccessToken,
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: () => mocks.native.value,
  },
}))

vi.mock('@capgo/capacitor-uploader', () => ({
  Uploader: {
    addListener: mocks.addListener,
    acknowledgeEvent: mocks.acknowledgeEvent,
    startUpload: mocks.startUpload,
  },
}))

vi.mock('../recording/nativeDraftFiles', () => ({
  nativeDraftFileUri: vi.fn(async () => 'file:///data/drafts/native.m4a'),
}))

vi.mock('./uploadKeepAlive', () => ({
  startUploadKeepAlive: mocks.startUploadKeepAlive,
  stopUploadKeepAlive: mocks.stopUploadKeepAlive,
}))

vi.stubGlobal('fetch', mocks.fetch)

import type { LocalDraft } from '../recording/draftRepository'
import { uploadDraft } from './uploadDraft'

const memoryStore = new Map<string, string>()

vi.stubGlobal('localStorage', {
  getItem: (key: string) => memoryStore.get(key) ?? null,
  setItem: (key: string, value: string) => {
    memoryStore.set(key, value)
  },
  removeItem: (key: string) => {
    memoryStore.delete(key)
  },
  clear: () => {
    memoryStore.clear()
  },
})

afterEach(() => {
  vi.clearAllMocks()
  mocks.native.value = false
  mocks.eventHandler = null
  memoryStore.clear()
})

function mockNativeUploader() {
  mocks.addListener.mockImplementation(async (_name: string, handler: (event: unknown) => void) => {
    mocks.eventHandler = handler
    return { remove: mocks.removeListener }
  })
  mocks.startUpload.mockImplementation(async () => {
    queueMicrotask(() => {
      mocks.eventHandler?.({
        id: 'upload-1',
        name: 'uploading',
        payload: { percent: 40 },
      })
      mocks.eventHandler?.({
        id: 'upload-1',
        name: 'completed',
        eventId: 'event-1',
        payload: { statusCode: 201 },
      })
    })
    return { id: 'upload-1' }
  })
}

describe('Draft upload', () => {
  it('sends browser audio and idempotency metadata to the authenticated API', async () => {
    const draft: LocalDraft = {
      id: 'local-draft-id',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 2700,
      mimeType: 'audio/webm',
      sizeBytes: 7,
      audio: new Blob(['sermon'], { type: 'audio/webm' }),
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: 'server-sermon-id',
          source_draft_id: draft.id,
          processing_status: 'uploaded',
        }),
        { status: 201 },
      ),
    )

    await expect(uploadDraft(draft)).resolves.toMatchObject({
      id: 'server-sermon-id',
      processing_status: 'uploaded',
    })

    expect(mocks.authorizedAccessToken).toHaveBeenCalledOnce()
    expect(mocks.fetch).toHaveBeenCalledOnce()
    const [url, options] = mocks.fetch.mock.calls[0] as unknown as [
      string,
      RequestInit & { body: FormData },
    ]
    expect(url).toBe('http://api.example.test/api/sermons/')
    expect(options.headers).toEqual({ Authorization: 'Bearer access-token' })
    expect(options.body.get('source_draft_id')).toBe(draft.id)
    expect(options.body.get('captured_at')).toBe(draft.createdAt)
    expect(options.body.get('duration_seconds')).toBe('2700')
    expect(options.body.get('capture_latitude')).toBeNull()
    expect(options.body.get('capture_longitude')).toBeNull()
    expect(options.body.get('audio')).toBeInstanceOf(Blob)
  })

  it('sends the place captured with the recording for nearby Church lookup later', async () => {
    const draft: LocalDraft = {
      id: 'placed-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 2700,
      mimeType: 'audio/webm',
      sizeBytes: 7,
      latitude: 39.9526,
      longitude: -75.1652,
      audio: new Blob(['sermon'], { type: 'audio/webm' }),
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: 'server-sermon-id',
          source_draft_id: draft.id,
          processing_status: 'uploaded',
        }),
        { status: 201 },
      ),
    )

    await uploadDraft(draft)

    const [, options] = mocks.fetch.mock.calls[0] as unknown as [
      string,
      RequestInit & { body: FormData },
    ]
    expect(options.body.get('capture_latitude')).toBe('39.952600')
    expect(options.body.get('capture_longitude')).toBe('-75.165200')
  })

  it('keeps the local Draft when the API rejects an upload', async () => {
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ audio: ['Unsupported audio.'] }), { status: 400 }),
    )

    const draft: LocalDraft = {
      id: 'failed-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 10,
      mimeType: 'audio/webm',
      sizeBytes: 7,
      audio: new Blob(['sermon'], { type: 'audio/webm' }),
    }

    await expect(uploadDraft(draft)).rejects.toThrow('Unsupported audio.')
  })

  it('uploads native Draft files in the background without loading them into JavaScript memory', async () => {
    mocks.native.value = true
    mockNativeUploader()
    mocks.fetch
      .mockResolvedValueOnce(new Response('{}', { status: 400 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 'native-sermon',
            source_draft_id: 'native-draft',
            processing_status: 'uploaded',
          }),
          { status: 200 },
        ),
      )

    const draft: LocalDraft = {
      id: 'native-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 2700,
      mimeType: 'audio/mp4',
      sizeBytes: 1024,
      audioPath: 'drafts/native.m4a',
    }

    const progress: number[] = []
    await expect(uploadDraft(draft, (value) => progress.push(value))).resolves.toMatchObject({
      id: 'native-sermon',
    })

    expect(mocks.startUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        fileField: 'audio',
        filePath: 'file:///data/drafts/native.m4a',
        headers: { Authorization: 'Bearer access-token' },
        method: 'POST',
        mimeType: 'audio/mp4',
        parameters: {
          source_draft_id: 'native-draft',
          captured_at: draft.createdAt,
          duration_seconds: '2700',
        },
        serverUrl: 'http://api.example.test/api/sermons/',
        uploadType: 'multipart',
        maxRetries: 2,
      }),
    )
    expect(mocks.acknowledgeEvent).toHaveBeenCalledWith({ eventId: 'event-1' })
    expect(mocks.startUploadKeepAlive).toHaveBeenCalledOnce()
    expect(mocks.stopUploadKeepAlive).toHaveBeenCalledOnce()
    expect(mocks.removeListener).toHaveBeenCalledOnce()
    expect(progress).toContain(0.4)
    expect(memoryStore.get('pewcorder.activeUploadDraftId')).toBeUndefined()
  })

  it('recovers when a prior native upload already created the Sermon', async () => {
    mocks.native.value = true
    mocks.fetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: 'already-there',
          source_draft_id: 'native-draft',
          processing_status: 'processing',
        }),
        { status: 200 },
      ),
    )
    const draft: LocalDraft = {
      id: 'native-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 392,
      mimeType: 'audio/mp4',
      sizeBytes: 1024,
      audioPath: 'drafts/native.m4a',
    }

    await expect(uploadDraft(draft)).resolves.toMatchObject({ id: 'already-there' })
    expect(mocks.startUpload).not.toHaveBeenCalled()
  })

  it('surfaces a clear interrupt message when the background upload fails', async () => {
    mocks.native.value = true
    mocks.addListener.mockImplementation(async (_name: string, handler: (event: unknown) => void) => {
      mocks.eventHandler = handler
      return { remove: mocks.removeListener }
    })
    mocks.startUpload.mockImplementation(async () => {
      queueMicrotask(() => {
        mocks.eventHandler?.({
          id: 'upload-1',
          name: 'failed',
          eventId: 'event-fail',
          payload: { error: 'The network connection was lost.' },
        })
      })
      return { id: 'upload-1' }
    })
    mocks.fetch
      .mockResolvedValueOnce(new Response('{}', { status: 400 }))
      .mockResolvedValueOnce(new Response('{}', { status: 400 }))

    const draft: LocalDraft = {
      id: 'native-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 392,
      mimeType: 'audio/mp4',
      sizeBytes: 1024,
      audioPath: 'drafts/native.m4a',
    }

    await expect(uploadDraft(draft)).rejects.toThrow(/interrupted|try Process again/i)
    expect(mocks.startUploadKeepAlive).toHaveBeenCalledOnce()
    expect(mocks.stopUploadKeepAlive).toHaveBeenCalledOnce()
  })
})
