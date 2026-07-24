/** Map a pointer X position on a seek track to a 0–1 playback ratio. */
export function seekRatioFromClientX(track: HTMLElement, clientX: number): number {
  const rect = track.getBoundingClientRect()
  if (rect.width <= 0) return 0
  return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
}

/** Format seconds as mm:ss or h:mm:ss for regenerate window inputs. */
export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = total % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}

/** Parse mm:ss or h:mm:ss into seconds; returns null when invalid. */
export function parseClock(value: string): number | null {
  const parts = value
    .trim()
    .split(':')
    .map((part) => Number(part))
  if (parts.length < 2 || parts.length > 3) return null
  if (parts.some((part) => !Number.isFinite(part) || part < 0)) return null
  if (parts.length === 2) {
    const [minutes, seconds] = parts as [number, number]
    if (seconds >= 60) return null
    return minutes * 60 + seconds
  }
  const [hours, minutes, seconds] = parts as [number, number, number]
  if (minutes >= 60 || seconds >= 60) return null
  return hours * 3600 + minutes * 60 + seconds
}
