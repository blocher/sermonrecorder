import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  checkPermissions: vi.fn(),
  getCurrentPosition: vi.fn(),
  requestPermissions: vi.fn(),
}))

vi.mock('@capacitor/geolocation', () => ({
  Geolocation: {
    checkPermissions: mocks.checkPermissions,
    getCurrentPosition: mocks.getCurrentPosition,
    requestPermissions: mocks.requestPermissions,
  },
}))

import { captureRecordingLocation } from './captureRecordingLocation'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('captureRecordingLocation', () => {
  it('stores a fresh high-accuracy fix after permission is granted', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ location: 'prompt' })
    mocks.requestPermissions.mockResolvedValueOnce({ location: 'granted' })
    mocks.getCurrentPosition.mockResolvedValueOnce({
      coords: { latitude: 39.95, longitude: -75.16 },
    })

    await expect(captureRecordingLocation()).resolves.toEqual({
      status: 'captured',
      latitude: 39.95,
      longitude: -75.16,
    })
    expect(mocks.getCurrentPosition).toHaveBeenCalledWith({
      enableHighAccuracy: true,
      timeout: 12_000,
      maximumAge: 0,
    })
  })

  it('still reads a fix on web when requestPermissions is unimplemented', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ location: 'prompt' })
    mocks.requestPermissions.mockRejectedValueOnce(new Error('Not implemented on web.'))
    mocks.getCurrentPosition.mockResolvedValueOnce({
      coords: { latitude: 39.95, longitude: -75.16 },
    })

    await expect(captureRecordingLocation()).resolves.toEqual({
      status: 'captured',
      latitude: 39.95,
      longitude: -75.16,
    })
  })

  it('falls back to a coarser fix when a fresh GPS reading fails', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ location: 'granted' })
    mocks.getCurrentPosition
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce({
        coords: { latitude: 40.0, longitude: -75.1 },
      })

    await expect(captureRecordingLocation()).resolves.toEqual({
      status: 'captured',
      latitude: 40.0,
      longitude: -75.1,
    })
    expect(mocks.getCurrentPosition).toHaveBeenNthCalledWith(2, {
      enableHighAccuracy: false,
      timeout: 12_000,
      maximumAge: 60_000,
    })
  })

  it('reports denial without throwing when permission stays off', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ location: 'denied' })

    await expect(captureRecordingLocation()).resolves.toEqual({ status: 'denied' })
    expect(mocks.getCurrentPosition).not.toHaveBeenCalled()
  })

  it('reports unavailability when the device fix fails', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ location: 'granted' })
    mocks.getCurrentPosition
      .mockRejectedValueOnce(new Error('timeout'))
      .mockRejectedValueOnce(new Error('unavailable'))

    await expect(captureRecordingLocation()).resolves.toEqual({ status: 'unavailable' })
  })
})
