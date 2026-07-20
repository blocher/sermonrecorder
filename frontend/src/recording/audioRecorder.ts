import { Capacitor } from '@capacitor/core'
import { BrowserAudioRecorder, supportsAudioRecording as supportsBrowserRecording } from './browserAudioRecorder'
import { NativeAudioRecorder } from './nativeAudioRecorder'
import type { DraftAudioInput } from './draftRepository'

export interface AudioCapture {
  audio: DraftAudioInput
  durationSeconds?: number
}

export interface AudioRecorder {
  start(): Promise<void>
  stop(): Promise<AudioCapture>
  cancel(): Promise<void>
  isActive(): Promise<boolean>
}

class BrowserRecorderAdapter implements AudioRecorder {
  private readonly recorder = new BrowserAudioRecorder()

  async start(): Promise<void> {
    await this.recorder.start()
  }

  async stop(): Promise<AudioCapture> {
    return { audio: await this.recorder.stop() }
  }

  async cancel(): Promise<void> {
    this.recorder.cancel()
  }

  async isActive(): Promise<boolean> {
    return this.recorder.isRecording
  }
}

export function createAudioRecorder(): AudioRecorder {
  return Capacitor.isNativePlatform() ? new NativeAudioRecorder() : new BrowserRecorderAdapter()
}

export function supportsAudioRecording(): boolean {
  return Capacitor.isNativePlatform() || supportsBrowserRecording()
}
