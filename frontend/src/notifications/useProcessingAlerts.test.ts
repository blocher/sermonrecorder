import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  native: true,
  platform: 'ios',
  permissions: { receive: 'prompt' },
  listeners: new Map<string, (payload: never) => void>(),
  addListener: vi.fn(async (event: string, listener: (payload: never) => void) => {
    mocks.listeners.set(event, listener)
    return { remove: vi.fn() }
  }),
  checkPermissions: vi.fn(),
  requestPermissions: vi.fn(),
  register: vi.fn(async () => undefined),
  unregister: vi.fn(async () => undefined),
  fetch: vi.fn(),
  authorizedAccessToken: vi.fn(async () => 'access-token'),
  refreshAuthorizedAccessToken: vi.fn(async () => 'refreshed-token'),
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: () => mocks.native,
    getPlatform: () => mocks.platform,
  },
}))

vi.mock('@capacitor/push-notifications', () => ({
  PushNotifications: {
    addListener: mocks.addListener,
    checkPermissions: mocks.checkPermissions,
    requestPermissions: mocks.requestPermissions,
    register: mocks.register,
    unregister: mocks.unregister,
  },
}))

vi.mock('../auth/useAuth', () => ({
  API_BASE_URL: 'http://api.example.test',
  authorizedAccessToken: mocks.authorizedAccessToken,
  refreshAuthorizedAccessToken: mocks.refreshAuthorizedAccessToken,
}))

vi.stubGlobal('fetch', mocks.fetch)

const stored = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (key: string) => stored.get(key) ?? null,
  setItem: (key: string, value: string) => stored.set(key, value),
  removeItem: (key: string) => stored.delete(key),
})

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  stored.clear()
  mocks.native = true
  mocks.platform = 'ios'
  mocks.permissions = { receive: 'prompt' }
  mocks.listeners.clear()
  mocks.checkPermissions.mockImplementation(async () => mocks.permissions)
  mocks.requestPermissions.mockImplementation(async () => ({ receive: 'granted' }))
})

describe('native Sermon processing alerts', () => {
  it('requests permission and privately registers the native token', async () => {
    mocks.fetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ id: 'registration-id', platform: 'ios', active: true }),
        { status: 201 },
      ),
    )
    const alerts = await import('./useProcessingAlerts')

    await alerts.enableProcessingAlerts()
    mocks.listeners.get('registration')?.({ value: 'native-token' } as never)

    await vi.waitFor(() => expect(alerts.useProcessingAlerts().enabled.value).toBe(true))
    expect(mocks.requestPermissions).toHaveBeenCalledOnce()
    expect(mocks.register).toHaveBeenCalledOnce()
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/auth/devices/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ platform: 'ios', token: 'native-token' }),
        headers: expect.objectContaining({ Authorization: 'Bearer access-token' }),
      }),
    )
    expect(stored.get('pewcorder-device-registration-id')).toBe('registration-id')
  })

  it('opens the private Sermon selected from an alert and disconnects on sign-out', async () => {
    stored.set('pewcorder-device-registration-id', 'registration-id')
    mocks.permissions = { receive: 'granted' }
    mocks.fetch.mockResolvedValueOnce(new Response(null, { status: 204 }))
    const openSermon = vi.fn()
    const alerts = await import('./useProcessingAlerts')

    await alerts.initializeProcessingAlerts(openSermon)
    mocks.listeners.get('pushNotificationActionPerformed')?.({
      notification: { data: { sermon_id: 'ready-sermon' } },
    } as never)
    await alerts.disconnectProcessingAlerts()

    expect(openSermon).toHaveBeenCalledWith('ready-sermon')
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://api.example.test/api/auth/devices/registration-id/',
      expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: 'Bearer access-token' },
      }),
    )
    expect(stored.has('pewcorder-device-registration-id')).toBe(false)
    expect(mocks.unregister).toHaveBeenCalledOnce()
  })

  it('does nothing in the browser', async () => {
    mocks.native = false
    const alerts = await import('./useProcessingAlerts')

    await alerts.enableProcessingAlerts()

    expect(alerts.useProcessingAlerts().available).toBe(false)
    expect(mocks.addListener).not.toHaveBeenCalled()
    expect(mocks.checkPermissions).not.toHaveBeenCalled()
    expect(mocks.fetch).not.toHaveBeenCalled()
  })
})
