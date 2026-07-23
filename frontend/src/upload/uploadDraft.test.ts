import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  authorizedAccessToken: vi.fn(async () => 'access-token'),
  fetch: vi.fn(),
  native: { value: false },
  removeListener: vi.fn(),
  uploadFile: vi.fn(),
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

vi.mock('@capacitor/file-transfer', () => ({
  FileTransfer: {
    addListener: vi.fn(async () => ({ remove: mocks.removeListener })),
    uploadFile: mocks.uploadFile,
  },
}))

vi.mock('../recording/nativeDraftFiles', () => ({
  nativeDraftFileUri: vi.fn(async () => 'file:///data/drafts/native.m4a'),
}))

vi.stubGlobal('fetch', mocks.fetch)

import type { LocalDraft } from '../recording/draftRepository'
import { uploadDraft } from './uploadDraft'

afterEach(() => {
  vi.clearAllMocks()
  mocks.native.value = false
})

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
    expect(options.body.get('audio')).toBeInstanceOf(Blob)
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

  it('streams native Draft files without loading them into JavaScript memory', async () => {
    mocks.native.value = true
    mocks.uploadFile.mockResolvedValueOnce({
      response: JSON.stringify({
        id: 'native-sermon',
        source_draft_id: 'native-draft',
        processing_status: 'uploaded',
      }),
    })
    const draft: LocalDraft = {
      id: 'native-draft',
      createdAt: '2026-07-20T15:30:00.000Z',
      durationSeconds: 2700,
      mimeType: 'audio/mp4',
      sizeBytes: 1024,
      audioPath: 'drafts/native.m4a',
    }

    await expect(uploadDraft(draft)).resolves.toMatchObject({ id: 'native-sermon' })

    expect(mocks.uploadFile).toHaveBeenCalledWith(
      expect.objectContaining({
        chunkedMode: false,
        fileKey: 'audio',
        headers: { Authorization: 'Bearer access-token' },
        mimeType: 'audio/mp4',
        params: {
          source_draft_id: 'native-draft',
          captured_at: draft.createdAt,
          duration_seconds: '2700',
        },
        path: 'file:///data/drafts/native.m4a',
      }),
    )
    expect(mocks.removeListener).toHaveBeenCalledOnce()
  })
})
