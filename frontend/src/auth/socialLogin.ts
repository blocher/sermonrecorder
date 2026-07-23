import { Capacitor } from '@capacitor/core'
import {
  SocialLogin,
  type InitializeOptions,
} from '@capgo/capacitor-social-login'

export type SocialProvider = 'apple' | 'google'

const platform = Capacitor.getPlatform()
const googleWebClientId = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID?.trim() ?? ''
const googleIosClientId = import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID?.trim() ?? ''
const appleClientId = import.meta.env.VITE_APPLE_CLIENT_ID?.trim() ?? ''
const appleRedirectUrl = import.meta.env.VITE_APPLE_REDIRECT_URL?.trim() ?? ''

function googleIsConfigured(): boolean {
  if (platform === 'ios') return Boolean(googleIosClientId)
  return Boolean(googleWebClientId)
}

function appleIsConfigured(): boolean {
  if (platform === 'ios') return true
  if (platform === 'android') return Boolean(appleClientId)
  return Boolean(appleClientId && appleRedirectUrl)
}

export const availableSocialProviders: SocialProvider[] = [
  ...(appleIsConfigured() ? (['apple'] as const) : []),
  ...(googleIsConfigured() ? (['google'] as const) : []),
]

let initialization: Promise<void> | undefined

function initialize(): Promise<void> {
  if (initialization) return initialization

  const options: InitializeOptions = {}
  if (googleIsConfigured()) {
    options.google = {
      webClientId: googleWebClientId || undefined,
      iOSClientId: googleIosClientId || undefined,
      iOSServerClientId: googleWebClientId || undefined,
      mode: 'online',
    }
  }
  if (appleIsConfigured()) {
    options.apple = {
      clientId: appleClientId || undefined,
      redirectUrl: platform === 'ios' ? '' : appleRedirectUrl || undefined,
      useBroadcastChannel: platform === 'android',
    }
  }

  initialization = SocialLogin.initialize(options)
  return initialization
}

export async function acquireSocialIdToken(
  provider: SocialProvider,
): Promise<string> {
  if (!availableSocialProviders.includes(provider)) {
    throw new Error(`${provider === 'apple' ? 'Apple' : 'Google'} sign-in is not configured.`)
  }
  await initialize()

  if (provider === 'google') {
    const login = await SocialLogin.login({
      provider: 'google',
      options: { scopes: ['email', 'profile'] },
    })
    if (login.result.responseType !== 'online' || !login.result.idToken) {
      throw new Error('Google did not return an identity credential.')
    }
    return login.result.idToken
  }

  const login = await SocialLogin.login({
    provider: 'apple',
    options: {
      scopes: ['email', 'name'],
      useBroadcastChannel: platform === 'android',
    },
  })
  if (!login.result.idToken) {
    throw new Error('Apple did not return an identity credential.')
  }
  return login.result.idToken
}
