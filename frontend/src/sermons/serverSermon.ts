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

export interface ServerReflection {
  id: string
  prompt: string
  content: string
  created_at: string
  updated_at: string
}

export interface ServerSermonDetail extends ServerSermon {
  audio_url: string
  transcript: ServerTranscript | null
  study_artifacts: ServerStudyArtifact[]
  scripture_references: ServerScriptureReference[]
  related_sermons: RelatedServerSermon[]
  reflections: ServerReflection[]
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

function responseError(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback
  for (const value of Object.values(data as Record<string, unknown>)) {
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return fallback
}

async function authorizedJson<T>(
  path: string,
  init: RequestInit = {},
  fallback = 'The request could not be completed.',
): Promise<T> {
  const request = (token: string) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...init.headers,
        Authorization: `Bearer ${token}`,
      },
    })

  let response = await request(await authorizedAccessToken())
  if (response.status === 401) {
    response = await request(await refreshAuthorizedAccessToken())
  }
  const data = (await response.json()) as unknown
  if (!response.ok) {
    throw new Error(responseError(data, fallback))
  }
  return data as T
}

export async function loadServerSermon(id: string): Promise<ServerSermonDetail> {
  return authorizedJson<ServerSermonDetail>(
    `/api/sermons/${encodeURIComponent(id)}/`,
    {},
    'This Sermon could not be opened.',
  )
}

export async function updateStudyArtifact(
  sermonId: string,
  kind: StudyArtifactKind,
  content: string,
): Promise<ServerStudyArtifact> {
  return authorizedJson<ServerStudyArtifact>(
    `/api/sermons/${encodeURIComponent(sermonId)}/artifacts/${kind}/`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
    'This Study artifact could not be saved.',
  )
}

export async function saveReflection(
  sermonId: string,
  reflection: Pick<ServerReflection, 'prompt' | 'content'> & { id?: string },
): Promise<ServerReflection> {
  const path = reflection.id
    ? `/api/sermons/${encodeURIComponent(sermonId)}/reflections/${encodeURIComponent(reflection.id)}/`
    : `/api/sermons/${encodeURIComponent(sermonId)}/reflections/`
  return authorizedJson<ServerReflection>(
    path,
    {
      method: reflection.id ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: reflection.prompt,
        content: reflection.content,
      }),
    },
    'Your Reflection could not be saved.',
  )
}
