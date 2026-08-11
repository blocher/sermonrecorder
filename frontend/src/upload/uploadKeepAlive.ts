import { Capacitor, registerPlugin } from '@capacitor/core'

interface UploadKeepAlivePlugin {
  start(): Promise<void>
  stop(): Promise<void>
}

const UploadKeepAlive = registerPlugin<UploadKeepAlivePlugin>('UploadKeepAlive')

/** Keep the device from sleeping / suspending network during a Draft upload. */
export async function startUploadKeepAlive(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  try {
    await UploadKeepAlive.start()
  } catch {
    // Older app builds without the native plugin still upload in the foreground.
  }
}

export async function stopUploadKeepAlive(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  try {
    await UploadKeepAlive.stop()
  } catch {
    // Ignore missing-plugin / already-stopped failures.
  }
}
