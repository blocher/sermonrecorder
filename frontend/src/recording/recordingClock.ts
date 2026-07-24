const RECORDING_STARTED_AT_KEY = 'pewcorder.recordingStartedAt'

let memoryStartedAt: number | undefined

function storageAvailable(): Storage | undefined {
  try {
    if (typeof localStorage === 'undefined') return undefined
    const probe = '__pewcorder_probe__'
    localStorage.setItem(probe, '1')
    localStorage.removeItem(probe)
    return localStorage
  } catch {
    return undefined
  }
}

export function wallClockNow(): number {
  return Date.now()
}

export function elapsedSecondsSince(startedAtMs: number, nowMs = wallClockNow()): number {
  if (!Number.isFinite(startedAtMs) || startedAtMs <= 0) return 0
  return Math.max(0, Math.floor((nowMs - startedAtMs) / 1_000))
}

export function persistRecordingStartedAt(startedAtMs: number): void {
  memoryStartedAt = startedAtMs
  const storage = storageAvailable()
  if (!storage) return
  try {
    storage.setItem(RECORDING_STARTED_AT_KEY, String(startedAtMs))
  } catch {
    // In-memory fallback already set.
  }
}

export function loadRecordingStartedAt(): number | undefined {
  const storage = storageAvailable()
  if (storage) {
    try {
      const raw = storage.getItem(RECORDING_STARTED_AT_KEY)
      if (raw) {
        const value = Number(raw)
        if (Number.isFinite(value) && value > 0) {
          memoryStartedAt = value
          return value
        }
      }
    } catch {
      // Fall through to memory.
    }
  }
  return memoryStartedAt
}

export function clearRecordingStartedAt(): void {
  memoryStartedAt = undefined
  const storage = storageAvailable()
  if (!storage) return
  try {
    storage.removeItem(RECORDING_STARTED_AT_KEY)
  } catch {
    // Ignore storage failures when clearing.
  }
}
