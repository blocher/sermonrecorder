import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  acquireSocialIdToken: vi.fn(async () => 'provider-id-token'),
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    getPlatform: () => 'ios',
  },
}))

vi.mock('./socialLogin', () => ({
  acquireSocialIdToken: mocks.acquireSocialIdToken,
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
})

describe('Pewcorder social session exchange', () => {
  it('exchanges a provider identity token for the normal private JWT session', async () => {
    const session = {
      access: 'pewcorder-access',
      refresh: 'pewcorder-refresh',
      user: {
        id: 'congregant-id',
        email: 'listener@example.com',
        display_name: 'A Listener',
      },
    }
    mocks.fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(session), { status: 200 }),
    )
    const auth = await import('./useAuth')

    await auth.useAuth().loginWithSocial('google')

    expect(mocks.acquireSocialIdToken).toHaveBeenCalledWith('google')
    expect(mocks.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/auth/social/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          provider: 'google',
          id_token: 'provider-id-token',
        }),
      }),
    )
    expect(auth.useAuth().user.value).toEqual(session.user)
    expect(JSON.parse(stored.get('pewcorder-auth-session') ?? '{}')).toEqual(
      session,
    )
  })
})
