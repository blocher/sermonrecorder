import { Geolocation } from '@capacitor/geolocation'
import {
  loadNearbyChurches,
  type ChurchSuggestion,
} from '../sermons/serverSermon'

export async function findNearbyChurches(): Promise<ChurchSuggestion[]> {
  try {
    let permission = await Geolocation.checkPermissions()
    if (permission.location === 'prompt' || permission.location === 'prompt-with-rationale') {
      permission = await Geolocation.requestPermissions({ permissions: ['location'] })
    }
    if (permission.location !== 'granted') {
      throw new Error(
        'Location permission is off. Choose a Church manually or enable location in system settings.',
      )
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
