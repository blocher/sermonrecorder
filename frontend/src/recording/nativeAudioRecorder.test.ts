import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  cancelRecording: vi.fn(),
  checkPermissions: vi.fn(),
  getRecordingStatus: vi.fn(),
  guardStart: vi.fn(),
  guardStop: vi.fn(),
  requestPermissions: vi.fn(),
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
}))

vi.mock('@capgo/capacitor-audio-recorder', () => ({
  AudioSessionMode: { Measurement: 'MEASUREMENT' },
  CapacitorAudioRecorder: {
    cancelRecording: mocks.cancelRecording,
    checkPermissions: mocks.checkPermissions,
    getRecordingStatus: mocks.getRecordingStatus,
    requestPermissions: mocks.requestPermissions,
    startRecording: mocks.startRecording,
    stopRecording: mocks.stopRecording,
  },
  RecordingStatus: {
    Inactive: 'INACTIVE',
    Paused: 'PAUSED',
    Recording: 'RECORDING',
  },
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    getPlatform: () => 'android',
  },
  registerPlugin: () => ({
    start: mocks.guardStart,
    stop: mocks.guardStop,
  }),
}))

import { NativeAudioRecorder } from './nativeAudioRecorder'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.checkPermissions.mockResolvedValue({ recordAudio: 'granted' })
  mocks.guardStart.mockResolvedValue(undefined)
  mocks.guardStop.mockResolvedValue(undefined)
  mocks.startRecording.mockResolvedValue(undefined)
  mocks.stopRecording.mockResolvedValue({
    duration: 42_400,
    uri: 'file:///tmp/sermon.m4a',
  })
})

describe('native audio recorder', () => {
  it('starts Android protection before native recording', async () => {
    const recorder = new NativeAudioRecorder()

    await recorder.start()

    expect(mocks.guardStart).toHaveBeenCalledOnce()
    expect(mocks.startRecording).toHaveBeenCalledWith({
      audioSessionMode: 'MEASUREMENT',
      bitRate: 128_000,
      sampleRate: 44_100,
    })
    expect(mocks.guardStart.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.startRecording.mock.invocationCallOrder[0],
    )
  })

  it('returns the native file and always releases Android protection', async () => {
    const recorder = new NativeAudioRecorder()

    await expect(recorder.stop()).resolves.toEqual({
      audio: {
        kind: 'native-file',
        mimeType: 'audio/mp4',
        uri: 'file:///tmp/sermon.m4a',
      },
      durationSeconds: 42,
    })
    expect(mocks.guardStop).toHaveBeenCalledOnce()
  })

  it('releases Android protection when recording cannot start', async () => {
    mocks.startRecording.mockRejectedValueOnce(new Error('native start failed'))
    const recorder = new NativeAudioRecorder()

    await expect(recorder.start()).rejects.toThrow('native start failed')
    expect(mocks.guardStop).toHaveBeenCalledOnce()
  })

  it('does not start when microphone permission is denied', async () => {
    mocks.checkPermissions.mockResolvedValueOnce({ recordAudio: 'prompt' })
    mocks.requestPermissions.mockResolvedValueOnce({ recordAudio: 'denied' })
    const recorder = new NativeAudioRecorder()

    await expect(recorder.start()).rejects.toMatchObject({ name: 'NotAllowedError' })
    expect(mocks.guardStart).not.toHaveBeenCalled()
    expect(mocks.startRecording).not.toHaveBeenCalled()
  })
})
