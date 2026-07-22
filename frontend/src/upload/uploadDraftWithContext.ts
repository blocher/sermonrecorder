import {
  createChurch,
  createPreacher,
  updateSermonContext,
  type OccasionKind,
} from '../sermons/serverSermon'
import type { LocalDraft } from '../recording/draftRepository'
import { uploadDraft, type UploadedSermon } from './uploadDraft'

type UploadProgress = (value: number) => void

export async function uploadDraftWithContext(
  draft: LocalDraft,
  onProgress?: UploadProgress,
): Promise<UploadedSermon> {
  const sermon = await uploadDraft(draft, onProgress)

  let churchId = draft.churchId ?? ''
  if (!churchId && draft.churchName?.trim()) {
    const church = await createChurch({
      name: draft.churchName.trim(),
      address: draft.churchAddress?.trim() ?? '',
      ...(draft.churchLatitude != null && draft.churchLongitude != null
        ? {
            latitude: draft.churchLatitude.toFixed(6),
            longitude: draft.churchLongitude.toFixed(6),
          }
        : {}),
    })
    churchId = church.id
  }

  let preacherId = draft.preacherId ?? ''
  if (!preacherId && draft.preacherName?.trim()) {
    const preacher = await createPreacher(draft.preacherName.trim())
    preacherId = preacher.id
  }

  const occasionKind = (draft.occasionKind ?? '') as OccasionKind | ''
  const liturgicalDay = draft.liturgicalDay?.trim() ?? ''

  if (churchId || preacherId || occasionKind || liturgicalDay) {
    await updateSermonContext(sermon.id, {
      church_id: churchId || null,
      preacher_id: preacherId || null,
      occasion_kind: occasionKind,
      liturgical_day: liturgicalDay,
    })
  }

  return sermon
}
