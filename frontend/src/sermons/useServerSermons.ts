import { computed, ref } from 'vue'
import { useAuth } from '../auth/useAuth'
import { loadInProgressSermons, type ServerSermon } from './serverSermon'

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
    sermons.value = await loadInProgressSermons()
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
  if (sermons.value.length === 0) return

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
    pendingSermons: computed(() => sermons.value),
    refresh,
    startPolling,
    stopPolling,
  }
}
