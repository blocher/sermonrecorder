import { Geolocation } from '@capacitor/geolocation'
import {
  loadNearbyChurches,
  type ChurchSuggestion,
} from '../sermons/serverSermon'

export async function findNearbyChurches(): Promise<ChurchSuggestion[]> {
  try {
    try {
      let permission = await Geolocation.checkPermissions()
      if (permission.location === 'prompt' || permission.location === 'prompt-with-rationale') {
        try {
          permission = await Geolocation.requestPermissions({ permissions: ['location'] })
        } catch {
          // Web: getCurrentPosition shows the browser prompt.
        }
      }
      if (permission.location === 'denied') {
        throw new Error(
          'Location permission is off. Choose a Church manually or enable location in system settings.',
        )
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes('Location permission is off')) {
        throw error
      }
      // Permissions API missing — continue to getCurrentPosition.
    }

    const position = await Geolocation.getCurrentPosition({
      enableHighAccuracy: true,
      timeout: 12_000,
      maximumAge: 60_000,
    })
    return loadNearbyChurches(position.coords.latitude, position.coords.longitude)
  } catch (error) {
    if (error instanceof Error) throw error
    throw new Error('Your location could not be read. Choose a Church manually.')
  }
}
