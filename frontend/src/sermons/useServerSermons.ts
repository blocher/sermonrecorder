import { computed, ref } from 'vue'
import {
  API_BASE_URL,
  authorizedAccessToken,
  refreshAuthorizedAccessToken,
  useAuth,
} from '../auth/useAuth'

export interface ServerSermon {
  id: string
  source_draft_id: string
  captured_at: string
  duration_seconds: number
  audio_mime_type: string
  audio_size_bytes: number
  processing_status: 'uploaded' | 'processing' | 'ready' | 'failed'
  processing_message: string
  created_at: string
  updated_at: string
}

const sermons = ref<ServerSermon[]>([])
const loading = ref(false)
const errorMessage = ref('')
let pollTimer: ReturnType<typeof setTimeout> | undefined
let polling = false

async function refresh(): Promise<void> {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated.value) {
    sermons.value = []
    errorMessage.value = ''
    return
  }

  loading.value = true
  try {
    const request = (token: string) =>
      fetch(`${API_BASE_URL}/api/sermons/`, {
        headers: { Authorization: `Bearer ${token}` },
      })

    let response = await request(await authorizedAccessToken())
    if (response.status === 401) {
      response = await request(await refreshAuthorizedAccessToken())
    }
    const data = (await response.json()) as unknown
    if (!response.ok) throw new Error('Your uploaded Sermons could not be refreshed.')
    sermons.value = data as ServerSermon[]
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Your uploaded Sermons could not be refreshed.'
  } finally {
    loading.value = false
    if (polling) schedulePoll()
  }
}

function schedulePoll(): void {
  if (!polling) return
  if (pollTimer) globalThis.clearTimeout(pollTimer)
  const hasPending = sermons.value.some(
    (sermon) => sermon.processing_status === 'uploaded' || sermon.processing_status === 'processing',
  )
  if (!hasPending) return

  pollTimer = globalThis.setTimeout(() => void refresh(), 15_000)
}

async function startPolling(): Promise<void> {
  polling = true
  await refresh()
}

function stopPolling(): void {
  polling = false
  if (pollTimer) globalThis.clearTimeout(pollTimer)
  pollTimer = undefined
}

export function useServerSermons() {
  return {
    sermons,
    loading,
    errorMessage,
    pendingSermons: computed(() =>
      sermons.value.filter((sermon) => sermon.processing_status !== 'ready'),
    ),
    refresh,
    startPolling,
    stopPolling,
  }
}
