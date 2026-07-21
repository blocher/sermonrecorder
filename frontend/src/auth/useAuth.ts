import { Capacitor } from '@capacitor/core'
import { computed, ref } from 'vue'
import {
  acquireSocialIdToken,
  type SocialProvider,
} from './socialLogin'

interface Congregant {
  id: string
  email: string
  display_name: string
}

interface AuthSession {
  access: string
  refresh: string
  user: Congregant
}

interface TokenPair {
  access: string
  refresh: string
}

const SESSION_KEY = 'pewcorder-auth-session'

export const API_BASE_URL = (
  import.meta.env.VITE_API_URL ??
  (Capacitor.getPlatform() === 'android' ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000')
).replace(/\/$/, '')

function storedSession(): AuthSession | undefined {
  try {
    const value = localStorage.getItem(SESSION_KEY)
    return value ? (JSON.parse(value) as AuthSession) : undefined
  } catch {
    return undefined
  }
}

const initialSession = storedSession()
const accessToken = ref(initialSession?.access ?? '')
const refreshToken = ref(initialSession?.refresh ?? '')
const user = ref<Congregant | undefined>(initialSession?.user)
const busy = ref(false)
const errorMessage = ref('')

function saveSession(): void {
  if (!accessToken.value || !refreshToken.value || !user.value) {
    localStorage.removeItem(SESSION_KEY)
    return
  }

  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({
      access: accessToken.value,
      refresh: refreshToken.value,
      user: user.value,
    } satisfies AuthSession),
  )
}

function responseError(data: unknown): string {
  if (!data || typeof data !== 'object') return 'The request could not be completed.'
  const values = Object.values(data as Record<string, unknown>)
  for (const value of values) {
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return 'The request could not be completed.'
}

async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = (await response.json()) as unknown
  if (!response.ok) throw new Error(responseError(data))
  return data as T
}

function tokenExpiresSoon(token: string): boolean {
  try {
    const payload = token.split('.')[1]
    if (!payload) return true
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const decoded = JSON.parse(atob(padded)) as { exp?: number }
    return !decoded.exp || decoded.exp * 1_000 < Date.now() + 60_000
  } catch {
    return true
  }
}

async function refreshAccessToken(): Promise<string> {
  if (!refreshToken.value) throw new Error('Sign in before uploading this Draft.')

  try {
    const tokens = await postJson<Partial<TokenPair>>('/api/auth/token/refresh/', {
      refresh: refreshToken.value,
    })
    if (!tokens.access) throw new Error('Your session could not be refreshed.')
    accessToken.value = tokens.access
    if (tokens.refresh) refreshToken.value = tokens.refresh
    saveSession()
    return accessToken.value
  } catch (error) {
    logout()
    throw error
  }
}

export async function refreshAuthorizedAccessToken(): Promise<string> {
  return refreshAccessToken()
}

export async function authorizedAccessToken(): Promise<string> {
  if (!accessToken.value) throw new Error('Sign in before uploading this Draft.')
  return tokenExpiresSoon(accessToken.value) ? refreshAccessToken() : accessToken.value
}

async function loadCurrentUser(): Promise<Congregant> {
  const token = await authorizedAccessToken()
  const response = await fetch(`${API_BASE_URL}/api/auth/me/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = (await response.json()) as unknown
  if (!response.ok) throw new Error(responseError(data))
  return data as Congregant
}

async function login(email: string, password: string): Promise<void> {
  busy.value = true
  errorMessage.value = ''
  try {
    const tokens = await postJson<TokenPair>('/api/auth/token/', { email, password })
    accessToken.value = tokens.access
    refreshToken.value = tokens.refresh
    user.value = await loadCurrentUser()
    saveSession()
  } catch (error) {
    logout()
    errorMessage.value = error instanceof Error ? error.message : 'Sign in failed.'
    throw error
  } finally {
    busy.value = false
  }
}

async function register(email: string, password: string, displayName: string): Promise<void> {
  busy.value = true
  errorMessage.value = ''
  try {
    const session = await postJson<AuthSession>('/api/auth/register/', {
      email,
      password,
      display_name: displayName,
    })
    accessToken.value = session.access
    refreshToken.value = session.refresh
    user.value = session.user
    saveSession()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Account creation failed.'
    throw error
  } finally {
    busy.value = false
  }
}

async function loginWithSocial(provider: SocialProvider): Promise<void> {
  busy.value = true
  errorMessage.value = ''
  try {
    const idToken = await acquireSocialIdToken(provider)
    const session = await postJson<AuthSession>('/api/auth/social/', {
      provider,
      id_token: idToken,
    })
    accessToken.value = session.access
    refreshToken.value = session.refresh
    user.value = session.user
    saveSession()
  } catch (error) {
    logout()
    errorMessage.value =
      error instanceof Error ? error.message : `${provider} sign-in failed.`
    throw error
  } finally {
    busy.value = false
  }
}

function logout(): void {
  accessToken.value = ''
  refreshToken.value = ''
  user.value = undefined
  errorMessage.value = ''
  saveSession()
}

export function useAuth() {
  return {
    user,
    busy,
    errorMessage,
    isAuthenticated: computed(() => Boolean(accessToken.value && user.value)),
    login,
    loginWithSocial,
    register,
    logout,
  }
}
