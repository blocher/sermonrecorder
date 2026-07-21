import {
  API_BASE_URL,
  authorizedAccessToken,
  refreshAuthorizedAccessToken,
} from '../auth/useAuth'

export type ProcessingStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

export interface ServerSermon {
  id: string
  source_draft_id: string
  captured_at: string
  duration_seconds: number
  audio_mime_type: string
  audio_size_bytes: number
  processing_status: ProcessingStatus
  processing_message: string
  short_summary: string
  tag_suggestions: string[]
  created_at: string
  updated_at: string
}

export interface ServerTranscriptSegment {
  start_seconds: number
  end_seconds: number
  text: string
}

export interface ServerTranscript {
  text: string
  segments: ServerTranscriptSegment[]
  updated_at: string
}

export type StudyArtifactKind =
  | 'short_summary'
  | 'long_summary'
  | 'outline'
  | 'adult_discussion_questions'
  | 'kids_discussion_questions'

export interface ServerStudyArtifact {
  kind: StudyArtifactKind
  content: string
  edited_at: string | null
  updated_at: string
}

export interface ServerScriptureReference {
  book: string
  chapter_start: number
  verse_start: number | null
  chapter_end: number | null
  verse_end: number | null
  display: string
}

export interface RelatedServerSermon {
  id: string
  captured_at: string
  score: number
  reason: string
}

export interface ServerSermonDetail extends ServerSermon {
  audio_url: string
  transcript: ServerTranscript | null
  study_artifacts: ServerStudyArtifact[]
  scripture_references: ServerScriptureReference[]
  related_sermons: RelatedServerSermon[]
}

export function serverSermonTitle(sermon: Pick<ServerSermon, 'captured_at'>): string {
  const captured = new Date(sermon.captured_at)
  return `${new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(captured)} Sermon`
}

export function serverSermonDuration(durationSeconds: number): string {
  const minutes = Math.max(1, Math.round(durationSeconds / 60))
  return `${minutes} min`
}

export async function loadServerSermon(id: string): Promise<ServerSermonDetail> {
  const request = (token: string) =>
    fetch(`${API_BASE_URL}/api/sermons/${encodeURIComponent(id)}/`, {
      headers: { Authorization: `Bearer ${token}` },
    })

  let response = await request(await authorizedAccessToken())
  if (response.status === 401) {
    response = await request(await refreshAuthorizedAccessToken())
  }
  if (!response.ok) {
    throw new Error(
      response.status === 404
        ? 'This Sermon is not in your private library.'
        : 'This Sermon could not be opened.',
    )
  }
  return (await response.json()) as ServerSermonDetail
}
