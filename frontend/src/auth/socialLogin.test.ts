import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  platform: 'ios',
  initialize: vi.fn(async () => undefined),
  login: vi.fn(),
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    getPlatform: () => mocks.platform,
  },
}))

vi.mock('@capgo/capacitor-social-login', () => ({
  SocialLogin: {
    initialize: mocks.initialize,
    login: mocks.login,
  },
}))

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  vi.unstubAllEnvs()
  mocks.platform = 'ios'
  vi.stubEnv('VITE_GOOGLE_WEB_CLIENT_ID', 'google-web-client')
  vi.stubEnv('VITE_GOOGLE_IOS_CLIENT_ID', 'google-ios-client')
  vi.stubEnv('VITE_APPLE_CLIENT_ID', 'com.pewcorder.web')
})

describe('native social identity credentials', () => {
  it('initializes once and returns Google and Apple identity tokens', async () => {
    mocks.login
      .mockResolvedValueOnce({
        provider: 'google',
        result: { responseType: 'online', idToken: 'google-id-token' },
      })
      .mockResolvedValueOnce({
        provider: 'apple',
        result: { idToken: 'apple-id-token' },
      })
    const social = await import('./socialLogin')

    await expect(social.acquireSocialIdToken('google')).resolves.toBe(
      'google-id-token',
    )
    await expect(social.acquireSocialIdToken('apple')).resolves.toBe(
      'apple-id-token',
    )

    expect(mocks.initialize).toHaveBeenCalledOnce()
    expect(mocks.initialize).toHaveBeenCalledWith({
      google: {
        webClientId: 'google-web-client',
        iOSClientId: 'google-ios-client',
        iOSServerClientId: 'google-web-client',
        mode: 'online',
      },
      apple: {
        clientId: 'com.pewcorder.web',
        redirectUrl: '',
        useBroadcastChannel: false,
      },
    })
  })

  it('rejects a provider response without an identity token', async () => {
    mocks.login.mockResolvedValueOnce({
      provider: 'apple',
      result: { idToken: null },
    })
    const social = await import('./socialLogin')

    await expect(social.acquireSocialIdToken('apple')).rejects.toThrow(
      'Apple did not return an identity credential.',
    )
  })

  it('only offers configured providers outside iOS', async () => {
    mocks.platform = 'android'
    vi.stubEnv('VITE_GOOGLE_WEB_CLIENT_ID', '')
    vi.stubEnv('VITE_GOOGLE_IOS_CLIENT_ID', '')
    vi.stubEnv('VITE_APPLE_CLIENT_ID', '')

    const social = await import('./socialLogin')

    expect(social.availableSocialProviders).toEqual([])
    await expect(social.acquireSocialIdToken('google')).rejects.toThrow(
      'Google sign-in is not configured.',
    )
    expect(mocks.initialize).not.toHaveBeenCalled()
  })
})
