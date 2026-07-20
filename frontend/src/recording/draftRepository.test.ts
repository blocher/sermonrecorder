import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { vi } from 'vitest'

const nativeFiles = vi.hoisted(() => ({
  deleteNativeDraftFile: vi.fn(),
  persistNativeRecording: vi.fn(),
}))

vi.mock('./nativeDraftFiles', () => nativeFiles)

import {
  closeDraftDatabase,
  createDraft,
  deleteDraft,
  listDrafts,
} from './draftRepository'

async function deleteTestDatabase(): Promise<void> {
  await closeDraftDatabase()
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.deleteDatabase('pewcorder')
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
    request.onblocked = () => reject(new Error('The test Draft database is blocked.'))
  })
}

beforeEach(deleteTestDatabase)
beforeEach(() => {
  vi.clearAllMocks()
  nativeFiles.deleteNativeDraftFile.mockResolvedValue(undefined)
  nativeFiles.persistNativeRecording.mockResolvedValue({
    path: 'drafts/native-draft.m4a',
    sizeBytes: 2048,
  })
})
afterEach(deleteTestDatabase)

describe('local Draft repository', () => {
  it('persists recorded audio and returns newest Drafts first', async () => {
    const firstAudio = new Blob(['first recording'], { type: 'audio/webm' })
    const secondAudio = new Blob(['second recording'], { type: 'audio/mp4' })

    await createDraft(firstAudio, 41, new Date('2026-07-20T14:00:00.000Z'))
    await createDraft(secondAudio, 82, new Date('2026-07-20T15:00:00.000Z'))

    const drafts = await listDrafts()

    expect(drafts).toHaveLength(2)
    expect(drafts[0]).toMatchObject({
      createdAt: '2026-07-20T15:00:00.000Z',
      durationSeconds: 82,
      mimeType: 'audio/mp4',
      sizeBytes: secondAudio.size,
    })
    expect(await drafts[0].audio?.text()).toBe('second recording')
    expect(drafts[1].createdAt).toBe('2026-07-20T14:00:00.000Z')
  })

  it('deletes only the chosen Draft', async () => {
    const keep = await createDraft(
      new Blob(['keep'], { type: 'audio/webm' }),
      12,
      new Date('2026-07-20T14:00:00.000Z'),
    )
    const remove = await createDraft(
      new Blob(['remove'], { type: 'audio/webm' }),
      18,
      new Date('2026-07-20T15:00:00.000Z'),
    )

    await deleteDraft(remove.id)

    const drafts = await listDrafts()
    expect(drafts.map((draft) => draft.id)).toEqual([keep.id])
  })

  it('refuses to save an empty recording', async () => {
    await expect(createDraft(new Blob([], { type: 'audio/webm' }), 1)).rejects.toThrow(
      'contains no audio',
    )
    await expect(listDrafts()).resolves.toEqual([])
  })

  it('persists native file metadata without copying audio into IndexedDB', async () => {
    const draft = await createDraft(
      {
        kind: 'native-file',
        mimeType: 'audio/mp4',
        uri: 'file:///temporary/recording.m4a',
      },
      75,
    )

    expect(nativeFiles.persistNativeRecording).toHaveBeenCalledWith(
      'file:///temporary/recording.m4a',
      draft.id,
    )
    expect(draft).toMatchObject({
      audioPath: 'drafts/native-draft.m4a',
      durationSeconds: 75,
      mimeType: 'audio/mp4',
      sizeBytes: 2048,
    })
    expect(draft.audio).toBeUndefined()

    await deleteDraft(draft.id)
    expect(nativeFiles.deleteNativeDraftFile).toHaveBeenCalledWith('drafts/native-draft.m4a')
  })
})
