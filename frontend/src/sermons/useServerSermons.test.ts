import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  authorizedAccessToken: vi.fn(async () => 'server-token'),
  fetch: vi.fn(),
  isAuthenticated: { value: true },
  refreshAuthorizedAccessToken: vi.fn(async () => 'refreshed-token'),
}))

vi.mock('../auth/useAuth', () => ({
  API_BASE_URL: 'http://api.example.test',
  authorizedAccessToken: mocks.authorizedAccessToken,
  refreshAuthorizedAccessToken: mocks.refreshAuthorizedAccessToken,
  useAuth: () => ({ isAuthenticated: mocks.isAuthenticated }),
}))

vi.stubGlobal('fetch', mocks.fetch)

import { useServerSermons } from './useServerSermons'

const uploadedSermon = {
  id: 'server-sermon',
  source_draft_id: 'local-draft',
  captured_at: '2026-07-20T15:30:00Z',
  duration_seconds: 2700,
  audio_mime_type: 'audio/mp4',
  audio_size_bytes: 1024,
  processing_status: 'uploaded' as const,
  processing_message: 'Safely uploaded and waiting to process.',
  created_at: '2026-07-20T15:31:00Z',
  updated_at: '2026-07-20T15:31:00Z',
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  mocks.isAuthenticated.value = true
  useServerSermons().sermons.value = []
})

afterEach(() => {
  useServerSermons().stopPolling()
  vi.useRealTimers()
})

describe('server Sermon library', () => {
  it('loads the signed-in Congregant’s processing Sermons', async () => {
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify([uploadedSermon]), { status: 200 }),
    )
    const library = useServerSermons()

    await library.refresh()

    expect(mocks.fetch).toHaveBeenCalledWith('http://api.example.test/api/sermons/', {
      headers: { Authorization: 'Bearer server-token' },
    })
    expect(library.pendingSermons.value).toEqual([uploadedSermon])
  })

  it('polls pending Sermons until they become ready', async () => {
    mocks.fetch
      .mockResolvedValueOnce(new Response(JSON.stringify([uploadedSermon]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              ...uploadedSermon,
              processing_status: 'ready',
              processing_message: 'Ready to revisit.',
            },
          ]),
          { status: 200 },
        ),
      )
    const library = useServerSermons()

    await library.startPolling()
    expect(library.pendingSermons.value).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mocks.fetch).toHaveBeenCalledTimes(2)
    expect(library.pendingSermons.value).toEqual([])
    expect(library.readySermons.value).toHaveLength(1)
  })

  it('refreshes an unexpectedly rejected access token once', async () => {
    mocks.fetch
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([uploadedSermon]), { status: 200 }))
    const library = useServerSermons()

    await library.refresh()

    expect(mocks.refreshAuthorizedAccessToken).toHaveBeenCalledOnce()
    expect(mocks.fetch).toHaveBeenLastCalledWith('http://api.example.test/api/sermons/', {
      headers: { Authorization: 'Bearer refreshed-token' },
    })
    expect(library.sermons.value).toEqual([uploadedSermon])
  })

  it('does not request another Congregant’s library while signed out', async () => {
    mocks.isAuthenticated.value = false
    const library = useServerSermons()

    await library.refresh()

    expect(mocks.fetch).not.toHaveBeenCalled()
    expect(library.sermons.value).toEqual([])
  })
})
