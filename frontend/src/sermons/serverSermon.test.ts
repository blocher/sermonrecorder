import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  authorizedAccessToken: vi.fn(async () => 'access-token'),
  fetch: vi.fn(),
  refreshAuthorizedAccessToken: vi.fn(async () => 'refreshed-token'),
}))

vi.mock('../auth/useAuth', () => ({
  API_BASE_URL: 'http://api.example.test',
  authorizedAccessToken: mocks.authorizedAccessToken,
  refreshAuthorizedAccessToken: mocks.refreshAuthorizedAccessToken,
}))

vi.stubGlobal('fetch', mocks.fetch)

import {
  loadServerSermon,
  serverSermonDuration,
  serverSermonTitle,
  type ServerSermonDetail,
} from './serverSermon'

const detail: ServerSermonDetail = {
  id: 'ready-sermon',
  source_draft_id: 'local-draft',
  captured_at: '2026-07-20T15:30:00Z',
  duration_seconds: 2700,
  audio_mime_type: 'audio/mp4',
  audio_size_bytes: 1024,
  processing_status: 'ready',
  processing_message: 'Ready to revisit.',
  short_summary: 'Grace meets us here.',
  tag_suggestions: ['Grace'],
  created_at: '2026-07-20T15:31:00Z',
  updated_at: '2026-07-20T15:35:00Z',
  audio_url: 'http://api.example.test/api/sermons/ready-sermon/audio/?token=signed',
  transcript: {
    text: 'Grace meets us here.',
    segments: [{ start_seconds: 0, end_seconds: 3, text: 'Grace meets us here.' }],
    updated_at: '2026-07-20T15:35:00Z',
  },
  study_artifacts: [],
  scripture_references: [],
  related_sermons: [],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('server Sermon detail', () => {
  it('loads owner-private processed content with the access token', async () => {
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(detail), { status: 200 }),
    )

    const result = await loadServerSermon('ready-sermon')

    expect(result).toEqual(detail)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/',
      { headers: { Authorization: 'Bearer access-token' } },
    )
  })

  it('refreshes a rejected access token once', async () => {
    mocks.fetch
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(detail), { status: 200 }))

    await loadServerSermon('ready-sermon')

    expect(mocks.refreshAuthorizedAccessToken).toHaveBeenCalledOnce()
    expect(mocks.fetch).toHaveBeenLastCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/',
      { headers: { Authorization: 'Bearer refreshed-token' } },
    )
  })

  it('uses clear date and duration labels without invented metadata', () => {
    expect(serverSermonTitle(detail)).toContain('Sermon')
    expect(serverSermonDuration(detail.duration_seconds)).toBe('45 min')
  })
})
