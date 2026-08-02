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
  createChurch,
  createPreacher,
  createSavedRecipient,
  loadChurches,
  loadNearbyChurches,
  loadPreachers,
  createShareLink,
  loadSavedRecipients,
  loadSharedSermon,
  loadShareLink,
  loadServerSermon,
  revokeShareLink,
  saveReflection,
  searchServerSermons,
  sendSermonEmail,
  serverSermonDuration,
  serverSermonTitle,
  deleteSermon,
  regenerateMagisteriumSermon,
  regenerateSermon,
  retrySermonProcessing,
  updateStudyArtifact,
  updateSermonContext,
  updateScriptureReferences,
  updateTags,
  updateTranscript,
  type ServerSermonDetail,
} from './serverSermon'

const detail: ServerSermonDetail = {
  id: 'ready-sermon',
  source_draft_id: 'local-draft',
  title: 'Grace Meets Us Here',
  captured_at: '2026-07-20T15:30:00Z',
  capture_latitude: null,
  capture_longitude: null,
  duration_seconds: 2700,
  audio_mime_type: 'audio/mp4',
  audio_size_bytes: 1024,
  church: null,
  preacher: null,
  occasion_kind: '',
  liturgical_day: '',
  processing_status: 'ready',
  processing_message: 'Ready to revisit.',
  short_summary: 'Grace meets us here.',
  tag_suggestions: ['Grace'],
  consider_start_seconds: null,
  consider_end_seconds: null,
  transcription_audio_source: 'original',
  created_at: '2026-07-20T15:31:00Z',
  updated_at: '2026-07-20T15:35:00Z',
  audio_url: 'http://api.example.test/api/sermons/ready-sermon/audio/?token=signed',
  has_playback_audio: false,
  has_isolated_audio: false,
  original_audio_url:
    'http://api.example.test/api/sermons/ready-sermon/audio/?token=signed&variant=original',
  playback_audio_url: '',
  isolated_audio_url: '',
  transcript: {
    text: 'Grace meets us here.',
    segments: [{ start_seconds: 0, end_seconds: 3, text: 'Grace meets us here.' }],
    display_text: 'Grace meets us here.',
    display_segments: [{ start_seconds: 0, end_seconds: 3, text: 'Grace meets us here.' }],
    raw_segments: [
      {
        speaker: 'A',
        start_seconds: 0,
        end_seconds: 3,
        text: 'Grace meets us here.',
      },
    ],
    updated_at: '2026-07-20T15:35:00Z',
  },
  study_artifacts: [],
  scripture_references: [],
  related_sermons: [],
  reflections: [],
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

  it('retries Failed Sermon processing with a POST', async () => {
    const retried = {
      ...detail,
      processing_status: 'uploaded' as const,
      processing_message: 'Safely uploaded and waiting to process.',
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(retried), { status: 200 }),
    )

    await expect(retrySermonProcessing('failed-sermon')).resolves.toEqual(retried)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/failed-sermon/retry/',
      { method: 'POST', headers: { Authorization: 'Bearer access-token' } },
    )
  })

  it('regenerates a Ready Sermon with a POST', async () => {
    const queued = {
      ...detail,
      processing_status: 'uploaded' as const,
      processing_message: 'Safely uploaded and waiting to process.',
      consider_start_seconds: 90,
      consider_end_seconds: 2400,
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(queued), { status: 200 }),
    )

    await expect(
      regenerateSermon('ready-sermon', {
        consider_start_seconds: 90,
        consider_end_seconds: 2400,
        transcription_audio_source: 'original',
      }),
    ).resolves.toEqual(queued)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/regenerate/',
      {
        method: 'POST',
        headers: {
          Authorization: 'Bearer access-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          consider_start_seconds: 90,
          consider_end_seconds: 2400,
          transcription_audio_source: 'original',
        }),
      },
    )
  })

  it('queues Magisterium-only regeneration with a POST', async () => {
    const status = {
      id: 'ready-sermon',
      processing_status: 'ready',
      processing_message: 'Ready to revisit.',
      updated_at: detail.updated_at,
      transcript_updated_at: detail.transcript?.updated_at ?? null,
      doctrinal_review_updated_at: null,
      related_sources_updated_at: null,
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(status), { status: 200 }),
    )

    await expect(regenerateMagisteriumSermon('ready-sermon')).resolves.toEqual(status)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/regenerate-magisterium/',
      { method: 'POST', headers: { Authorization: 'Bearer access-token' } },
    )
  })

  it('deletes a Sermon with DELETE', async () => {
    mocks.fetch.mockResolvedValueOnce(new Response(null, { status: 204 }))

    await expect(deleteSermon('ready-sermon')).resolves.toBeUndefined()
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/',
      { method: 'DELETE', headers: { Authorization: 'Bearer access-token' } },
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
    expect(serverSermonTitle(detail)).toBe('Grace Meets Us Here')
    expect(serverSermonTitle({ captured_at: detail.captured_at })).toContain('Sermon')
    expect(serverSermonDuration(detail.duration_seconds)).toBe('45 min')
  })

  it('searches Ready Sermons with private Library filters', async () => {
    const page = {
      count: 1,
      next: null,
      previous: null,
      results: [detail],
    }
    mocks.fetch.mockResolvedValueOnce(new Response(JSON.stringify(page), { status: 200 }))

    await expect(
      searchServerSermons({
        search: '  mustard welcome  ',
        church: 'church-id',
        preacher: '',
        occasion: 'sunday',
        tag: 'Welcome',
        date_from: '2026-01-01',
        date_to: '2026-01-31',
      }),
    ).resolves.toEqual(page)

    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/?processing_status=ready&search=mustard+welcome&church=church-id&occasion=sunday&tag=Welcome&date_from=2026-01-01&date_to=2026-01-31',
      { headers: { Authorization: 'Bearer access-token' } },
    )
  })

  it('requests later Ready Sermon pages', async () => {
    const page = {
      count: 41,
      next: null,
      previous: 'http://api.example.test/api/sermons/?processing_status=ready&page=1',
      results: [detail],
    }
    mocks.fetch.mockResolvedValueOnce(new Response(JSON.stringify(page), { status: 200 }))

    await expect(searchServerSermons({}, 2)).resolves.toEqual(page)

    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/?processing_status=ready&page=2',
      { headers: { Authorization: 'Bearer access-token' } },
    )
  })

  it('persists one independently edited Study artifact', async () => {
    const savedArtifact = {
      kind: 'short_summary' as const,
      content: 'My corrected summary.',
      edited_at: '2026-07-20T16:00:00Z',
      updated_at: '2026-07-20T16:00:00Z',
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(savedArtifact), { status: 200 }),
    )

    const result = await updateStudyArtifact(
      'ready-sermon',
      'short_summary',
      'My corrected summary.',
    )

    expect(result).toEqual(savedArtifact)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/artifacts/short_summary/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ content: 'My corrected summary.' }),
      }),
    )
  })

  it('saves corrected Transcript words against existing timestamps', async () => {
    const corrected = {
      ...detail.transcript!,
      text: 'Corrected words.',
      segments: [{ start_seconds: 0, end_seconds: 3, text: 'Corrected words.' }],
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(corrected), { status: 200 }),
    )

    await expect(
      updateTranscript('ready-sermon', [
        { start_seconds: 0, text: 'Corrected words.' },
      ]),
    ).resolves.toEqual(corrected)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/transcript/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          segments: [{ start_seconds: 0, text: 'Corrected words.' }],
        }),
      }),
    )
  })

  it('replaces AI Tag suggestions with the Congregant curated list', async () => {
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ tags: ['Mercy', 'Prayer'] }), {
        status: 200,
      }),
    )

    await expect(
      updateTags('ready-sermon', ['Mercy', 'Prayer']),
    ).resolves.toEqual(['Mercy', 'Prayer'])
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/tags/',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ tags: ['Mercy', 'Prayer'] }),
      }),
    )
  })

  it('replaces AI Scripture references with structured corrections', async () => {
    const corrected = [
      {
        book: 'Romans',
        chapter_start: 8,
        verse_start: 31,
        chapter_end: null,
        verse_end: 39,
        display: 'Romans 8:31–39',
      },
    ]
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ scripture_references: corrected }), {
        status: 200,
      }),
    )

    await expect(
      updateScriptureReferences('ready-sermon', [
        {
          book: 'Romans',
          chapter_start: 8,
          verse_start: 31,
          chapter_end: null,
          verse_end: 39,
        },
      ]),
    ).resolves.toEqual(corrected)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/scripture-references/',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          scripture_references: [
            {
              book: 'Romans',
              chapter_start: 8,
              verse_start: 31,
              chapter_end: null,
              verse_end: 39,
            },
          ],
        }),
      }),
    )
  })

  it('creates a private Reflection with its prompt', async () => {
    const reflection = {
      id: 'reflection-id',
      prompt: 'Where is grace asking me to act?',
      content: 'I will make room.',
      created_at: '2026-07-20T16:00:00Z',
      updated_at: '2026-07-20T16:00:00Z',
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(reflection), { status: 201 }),
    )

    const result = await saveReflection('ready-sermon', {
      prompt: reflection.prompt,
      content: reflection.content,
    })

    expect(result).toEqual(reflection)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/reflections/',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('creates, inspects, and revokes an owner-managed Share Link', async () => {
    const shareLink = {
      url: 'https://listen.example.test/share/signed-token',
      created_at: '2026-07-20T16:00:00Z',
    }
    mocks.fetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ share_link: shareLink }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(shareLink), { status: 201 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))

    await expect(loadShareLink('ready-sermon')).resolves.toEqual(shareLink)
    await expect(createShareLink('ready-sermon')).resolves.toEqual(shareLink)
    await expect(revokeShareLink('ready-sermon')).resolves.toBeUndefined()

    expect(mocks.fetch).toHaveBeenLastCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/share/',
      expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: 'Bearer access-token' },
      }),
    )
  })

  it('loads a public shared Sermon without an authorization header', async () => {
    const sharedDetail = {
      captured_at: detail.captured_at,
      duration_seconds: detail.duration_seconds,
      church: null,
      preacher: null,
      occasion_kind: '',
      liturgical_day: '',
      audio_url: 'http://api.example.test/api/shares/signed-token/audio/',
      has_playback_audio: false,
      has_isolated_audio: false,
      original_audio_url:
        'http://api.example.test/api/shares/signed-token/audio/?variant=original',
      playback_audio_url: '',
      isolated_audio_url: '',
      transcript: detail.transcript,
      study_artifacts: [],
      scripture_references: [],
      tag_suggestions: ['Grace'],
      updated_at: detail.updated_at,
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(sharedDetail), { status: 200 }),
    )

    await expect(loadSharedSermon('signed/token')).resolves.toEqual(sharedDetail)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/shares/signed%2Ftoken/',
    )
  })

  it('loads and creates reusable email recipients', async () => {
    const recipient = {
      id: 'recipient-id',
      name: 'Family',
      email: 'family@example.com',
      created_at: '2026-07-20T16:00:00Z',
      updated_at: '2026-07-20T16:00:00Z',
    }
    mocks.fetch
      .mockResolvedValueOnce(new Response(JSON.stringify([recipient]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(recipient), { status: 201 }))

    await expect(loadSavedRecipients()).resolves.toEqual([recipient])
    await expect(
      createSavedRecipient({ name: recipient.name, email: recipient.email }),
    ).resolves.toEqual(recipient)
    expect(mocks.fetch).toHaveBeenLastCalledWith(
      'http://api.example.test/api/auth/recipients/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: recipient.name, email: recipient.email }),
      }),
    )
  })

  it('sends a Sermon handout to selected saved recipients', async () => {
    const result = {
      sent_count: 2,
      share_url: 'https://listen.example.test/share/signed-token',
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(result), { status: 200 }),
    )

    await expect(
      sendSermonEmail('ready-sermon', {
        recipient_ids: ['anna', 'family'],
        subject: 'A sermon worth revisiting',
        note: 'I thought of you.',
      }),
    ).resolves.toEqual(result)
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/email/',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer access-token' }),
      }),
    )
  })

  it('reuses personal Church and Preacher records when saving Sermon context', async () => {
    const church = {
      id: 'church-id',
      name: 'Grace Parish',
      address: '1 Main Street',
      latitude: null,
      longitude: null,
      created_at: '2026-07-20T16:00:00Z',
      updated_at: '2026-07-20T16:00:00Z',
    }
    const preacher = {
      id: 'preacher-id',
      name: 'Rev. Miriam Cho',
      created_at: '2026-07-20T16:00:00Z',
      updated_at: '2026-07-20T16:00:00Z',
    }
    const contextualized = {
      ...detail,
      church,
      preacher,
      occasion_kind: 'sunday',
      liturgical_day: 'Third Sunday of Ordinary Time',
    }
    mocks.fetch
      .mockResolvedValueOnce(new Response(JSON.stringify([church]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(church), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([preacher]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(preacher), { status: 201 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(contextualized), { status: 200 }),
      )

    await expect(loadChurches()).resolves.toEqual([church])
    await expect(
      createChurch({ name: church.name, address: church.address }),
    ).resolves.toEqual(church)
    await expect(loadPreachers()).resolves.toEqual([preacher])
    await expect(createPreacher(preacher.name)).resolves.toEqual(preacher)
    await expect(
      updateSermonContext('ready-sermon', {
        title: 'Bread for the Journey',
        church_id: church.id,
        preacher_id: preacher.id,
        occasion_kind: 'sunday',
        liturgical_day: 'Third Sunday of Ordinary Time',
      }),
    ).resolves.toEqual(contextualized)
    expect(mocks.fetch).toHaveBeenLastCalledWith(
      'http://api.example.test/api/sermons/ready-sermon/context/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          title: 'Bread for the Journey',
          church_id: church.id,
          preacher_id: preacher.id,
          occasion_kind: 'sunday',
          liturgical_day: 'Third Sunday of Ordinary Time',
        }),
      }),
    )
  })

  it('loads nearby Church suggestions without persisting the precise fix', async () => {
    const suggestion = {
      provider_id: 'osm:node:42',
      name: 'Grace Parish',
      address: '12 Cedar Lane',
      latitude: 40.001,
      longitude: -75.001,
      distance_meters: 140,
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify([suggestion]), { status: 200 }),
    )

    await expect(loadNearbyChurches(40, -75)).resolves.toEqual([suggestion])
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/sermons/churches/suggestions/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ latitude: 40, longitude: -75 }),
      }),
    )
  })
})
