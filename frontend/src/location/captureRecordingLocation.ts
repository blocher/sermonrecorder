import { Geolocation } from '@capacitor/geolocation'

export type LocationCaptureResult =
  | { status: 'captured'; latitude: number; longitude: number }
  | { status: 'denied' }
  | { status: 'unavailable' }

function isPermissionDenied(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError'
  }
  if (!(error instanceof Error)) return false
  return /denied|permission/i.test(error.message)
}

/**
 * Capture the device fix after recording stops.
 * Never call this to gate starting a recording.
 *
 * On web, Capacitor's requestPermissions() is unimplemented — the browser
 * permission prompt is triggered by getCurrentPosition() instead.
 */
export async function captureRecordingLocation(): Promise<LocationCaptureResult> {
  try {
    try {
      let permission = await Geolocation.checkPermissions()
      if (permission.location === 'prompt' || permission.location === 'prompt-with-rationale') {
        try {
          permission = await Geolocation.requestPermissions({ permissions: ['location'] })
        } catch {
          // Web: continue to getCurrentPosition, which shows the browser prompt.
        }
      }
      if (permission.location === 'denied') {
        return { status: 'denied' }
      }
    } catch {
      // Permissions API missing — prompt via getCurrentPosition.
    }

    try {
      const precise = await Geolocation.getCurrentPosition({
        enableHighAccuracy: true,
        timeout: 12_000,
        maximumAge: 0,
      })
      return {
        status: 'captured',
        latitude: precise.coords.latitude,
        longitude: precise.coords.longitude,
      }
    } catch (preciseError) {
      if (isPermissionDenied(preciseError)) return { status: 'denied' }

      // Fresh GPS can fail indoors; accept a slightly older / coarser fix.
      const fallback = await Geolocation.getCurrentPosition({
        enableHighAccuracy: false,
        timeout: 12_000,
        maximumAge: 60_000,
      })
      return {
        status: 'captured',
        latitude: fallback.coords.latitude,
        longitude: fallback.coords.longitude,
      }
    }
  } catch (error) {
    if (isPermissionDenied(error)) return { status: 'denied' }
    return { status: 'unavailable' }
  }
}
