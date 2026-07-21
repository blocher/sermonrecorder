import { Capacitor } from '@capacitor/core'
import {
  PushNotifications,
  type ActionPerformed,
  type PermissionStatus,
  type Token,
} from '@capacitor/push-notifications'
import { computed, ref } from 'vue'
import {
  API_BASE_URL,
  authorizedAccessToken,
  refreshAuthorizedAccessToken,
} from '../auth/useAuth'

type AlertState =
  | 'unavailable'
  | 'prompt'
  | 'denied'
  | 'registering'
  | 'registered'
  | 'error'

interface DeviceRegistration {
  id: string
  platform: 'ios' | 'android'
  active: boolean
}

const REGISTRATION_KEY = 'pewcorder-device-registration-id'
const available = Capacitor.isNativePlatform()
const state = ref<AlertState>(available ? 'prompt' : 'unavailable')
const errorMessage = ref('')
let initialization: Promise<void> | undefined
let openSermon: ((sermonId: string) => void) | undefined
let tokenSave: Promise<void> | undefined
let disconnecting = false

async function authorizedRequest(path: string, init: RequestInit): Promise<Response> {
  const request = (token: string) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...init.headers,
        Authorization: `Bearer ${token}`,
      },
    })
  let response = await request(await authorizedAccessToken())
  if (response.status === 401) {
    response = await request(await refreshAuthorizedAccessToken())
  }
  return response
}

async function saveNativeToken(token: Token): Promise<void> {
  const platform = Capacitor.getPlatform()
  if (platform !== 'ios' && platform !== 'android') return

  try {
    const response = await authorizedRequest('/api/auth/devices/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, token: token.value }),
    })
    if (!response.ok) throw new Error('This device could not be connected to completion alerts.')
    const registration = (await response.json()) as DeviceRegistration
    localStorage.setItem(REGISTRATION_KEY, registration.id)
    state.value = 'registered'
    errorMessage.value = ''
  } catch (error) {
    state.value = 'error'
    errorMessage.value =
      error instanceof Error ? error.message : 'Completion alerts could not be enabled.'
  }
}

function receivePermission(status: PermissionStatus): PermissionStatus['receive'] {
  state.value =
    status.receive === 'granted' ? 'registering' : status.receive === 'denied' ? 'denied' : 'prompt'
  return status.receive
}

export async function initializeProcessingAlerts(
  onOpenSermon?: (sermonId: string) => void,
): Promise<void> {
  if (onOpenSermon) openSermon = onOpenSermon
  if (!available) return
  initialization ??= setUpProcessingAlerts()
  await initialization
}

async function setUpProcessingAlerts(): Promise<void> {
  await PushNotifications.addListener('registration', (token) => {
    if (disconnecting) return
    tokenSave = saveNativeToken(token)
    void tokenSave
  })
  await PushNotifications.addListener('registrationError', (error) => {
    state.value = 'error'
    errorMessage.value = error.error
  })
  await PushNotifications.addListener('pushNotificationActionPerformed', (action: ActionPerformed) => {
    const sermonId = action.notification.data?.sermon_id
    if (typeof sermonId === 'string') openSermon?.(sermonId)
  })

  const permission = await PushNotifications.checkPermissions()
  const receive = receivePermission(permission)
  if (receive === 'granted' && localStorage.getItem(REGISTRATION_KEY)) {
    state.value = 'registered'
  }
}

export async function enableProcessingAlerts(): Promise<void> {
  if (!available) return
  await initializeProcessingAlerts()
  let permission = await PushNotifications.checkPermissions()
  if (permission.receive === 'prompt' || permission.receive === 'prompt-with-rationale') {
    permission = await PushNotifications.requestPermissions()
  }
  if (receivePermission(permission) !== 'granted') return

  errorMessage.value = ''
  await PushNotifications.register()
}

export async function syncProcessingAlerts(): Promise<void> {
  if (!available) return
  await initializeProcessingAlerts()
  const permission = await PushNotifications.checkPermissions()
  if (permission.receive !== 'granted') {
    receivePermission(permission)
    return
  }
  state.value = 'registering'
  await PushNotifications.register()
}

export async function disconnectProcessingAlerts(): Promise<void> {
  if (!available) return
  disconnecting = true
  try {
    await tokenSave
    const registrationId = localStorage.getItem(REGISTRATION_KEY)
    if (registrationId) {
      await authorizedRequest(`/api/auth/devices/${encodeURIComponent(registrationId)}/`, {
        method: 'DELETE',
      })
    }
  } finally {
    await PushNotifications.unregister().catch(() => undefined)
    localStorage.removeItem(REGISTRATION_KEY)
    state.value = 'prompt'
    tokenSave = undefined
    disconnecting = false
  }
}

export function useProcessingAlerts() {
  return {
    available,
    state,
    errorMessage,
    enabled: computed(() => state.value === 'registered'),
    enable: enableProcessingAlerts,
    disconnect: disconnectProcessingAlerts,
  }
}
