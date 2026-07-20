import {
  AudioSessionMode,
  CapacitorAudioRecorder,
  RecordingStatus,
} from '@capgo/capacitor-audio-recorder'
import { Capacitor, registerPlugin } from '@capacitor/core'
import type { AudioCapture, AudioRecorder } from './audioRecorder'

interface RecordingGuardPlugin {
  start(): Promise<void>
  stop(): Promise<void>
}

const RecordingGuard = registerPlugin<RecordingGuardPlugin>('RecordingGuard')

async function stopAndroidGuard(): Promise<void> {
  if (Capacitor.getPlatform() === 'android') await RecordingGuard.stop()
}

export class NativeAudioRecorder implements AudioRecorder {
  async start(): Promise<void> {
    const currentPermission = await CapacitorAudioRecorder.checkPermissions()
    const permission =
      currentPermission.recordAudio === 'granted'
        ? currentPermission
        : await CapacitorAudioRecorder.requestPermissions()

    if (permission.recordAudio !== 'granted') {
      throw new DOMException('Microphone permission was denied.', 'NotAllowedError')
    }

    if (Capacitor.getPlatform() === 'android') await RecordingGuard.start()

    try {
      await CapacitorAudioRecorder.startRecording({
        audioSessionMode: AudioSessionMode.Measurement,
        bitRate: 128_000,
        sampleRate: 44_100,
      })
    } catch (error) {
      await stopAndroidGuard()
      throw error
    }
  }

  async stop(): Promise<AudioCapture> {
    try {
      const result = await CapacitorAudioRecorder.stopRecording()
      if (!result.uri) throw new Error('The native recorder did not return an audio file.')

      return {
        audio: {
          kind: 'native-file',
          uri: result.uri,
          mimeType: 'audio/mp4',
        },
        durationSeconds:
          typeof result.duration === 'number' ? Math.max(1, Math.round(result.duration / 1_000)) : undefined,
      }
    } finally {
      await stopAndroidGuard()
    }
  }

  async cancel(): Promise<void> {
    try {
      await CapacitorAudioRecorder.cancelRecording()
    } finally {
      await stopAndroidGuard()
    }
  }

  async isActive(): Promise<boolean> {
    const { status } = await CapacitorAudioRecorder.getRecordingStatus()
    return status === RecordingStatus.Recording || status === RecordingStatus.Paused
  }
}
