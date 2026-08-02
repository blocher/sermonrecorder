/** Precise place captured when the Draft was recorded — not the listener's current GPS. */
export function recordingCapturePlace(sermon: {
  capture_latitude?: string | null
  capture_longitude?: string | null
}): { latitude: number; longitude: number } | null {
  if (sermon.capture_latitude == null || sermon.capture_longitude == null) {
    return null
  }
  const latitude = Number(sermon.capture_latitude)
  const longitude = Number(sermon.capture_longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null
  }
  return { latitude, longitude }
}
