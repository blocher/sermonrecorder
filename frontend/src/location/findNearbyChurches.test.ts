import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  checkPermissions: vi.fn(),
  requestPermissions: vi.fn(),
  getCurrentPosition: vi.fn(),
  loadNearbyChurches: vi.fn(),
}))

vi.mock('@capacitor/geolocation', () => ({
  Geolocation: {
    checkPermissions: mocks.checkPermissions,
    requestPermissions: mocks.requestPermissions,
    getCurrentPosition: mocks.getCurrentPosition,
  },
}))

vi.mock('../sermons/serverSermon', () => ({
  loadNearbyChurches: mocks.loadNearbyChurches,
}))

import { findNearbyChurches } from './findNearbyChurches'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('nearby Church location', () => {
  it('asks explicitly, reads one precise fix, and forwards only coordinates for lookup', async () => {
    const suggestions = [{ provider_id: 'osm:node:42', name: 'Grace Parish' }]
    mocks.checkPermissions.mockResolvedValue({ location: 'prompt' })
    mocks.requestPermissions.mockResolvedValue({ location: 'granted' })
    mocks.getCurrentPosition.mockResolvedValue({
      coords: { latitude: 40.001, longitude: -75.002 },
    })
    mocks.loadNearbyChurches.mockResolvedValue(suggestions)

    await expect(findNearbyChurches()).resolves.toEqual(suggestions)

    expect(mocks.requestPermissions).toHaveBeenCalledWith({ permissions: ['location'] })
    expect(mocks.getCurrentPosition).toHaveBeenCalledWith({
      enableHighAccuracy: true,
      timeout: 12_000,
      maximumAge: 60_000,
    })
    expect(mocks.loadNearbyChurches).toHaveBeenCalledWith(40.001, -75.002)
  })

  it('does not read location after permission is denied', async () => {
    mocks.checkPermissions.mockResolvedValue({ location: 'denied' })

    await expect(findNearbyChurches()).rejects.toThrow('Location permission is off')

    expect(mocks.getCurrentPosition).not.toHaveBeenCalled()
    expect(mocks.loadNearbyChurches).not.toHaveBeenCalled()
  })

  it('still reads a fix on web when requestPermissions is unimplemented', async () => {
    const suggestions = [{ provider_id: 'osm:node:42', name: 'Grace Parish' }]
    mocks.checkPermissions.mockResolvedValue({ location: 'prompt' })
    mocks.requestPermissions.mockRejectedValue(new Error('Not implemented on web.'))
    mocks.getCurrentPosition.mockResolvedValue({
      coords: { latitude: 40.001, longitude: -75.002 },
    })
    mocks.loadNearbyChurches.mockResolvedValue(suggestions)

    await expect(findNearbyChurches()).resolves.toEqual(suggestions)
    expect(mocks.getCurrentPosition).toHaveBeenCalledOnce()
  })
})
