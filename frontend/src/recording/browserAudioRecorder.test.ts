import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserAudioRecorder, supportsAudioRecording } from './browserAudioRecorder'

class FakeMediaRecorder extends EventTarget {
  static supportedTypes = new Set(['audio/webm', 'audio/mp4'])

  static isTypeSupported(type: string): boolean {
    return FakeMediaRecorder.supportedTypes.has(type)
  }

  readonly mimeType: string
  state: RecordingState = 'inactive'
  startTimeslice: number | undefined

  constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
    super()
    this.mimeType = options?.mimeType ?? 'audio/webm'
  }

  start(timeslice?: number): void {
    this.startTimeslice = timeslice
    this.state = 'recording'
  }

  stop(): void {
    const dataEvent = new Event('dataavailable')
    Object.defineProperty(dataEvent, 'data', {
      value: new Blob(['recorded sermon'], { type: this.mimeType }),
    })
    this.dispatchEvent(dataEvent)
    this.state = 'inactive'
    this.dispatchEvent(new Event('stop'))
  }
}

const stopTrack = vi.fn()
const getUserMedia = vi.fn(async () => {
  return {
    getTracks: () => [{ stop: stopTrack }],
  } as unknown as MediaStream
})

beforeEach(() => {
  stopTrack.mockClear()
  getUserMedia.mockClear()
  FakeMediaRecorder.supportedTypes = new Set(['audio/webm', 'audio/mp4'])
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia,
    },
  })
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('browser audio recorder', () => {
  it('prefers WebM over MP4 so Chromium does not write Opus-in-MP4', async () => {
    FakeMediaRecorder.supportedTypes = new Set([
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ])
    const recorder = new BrowserAudioRecorder()

    await recorder.start()
    const audio = await recorder.stop()

    expect(audio.type).toBe('audio/webm;codecs=opus')
  })

  it('captures an audio Blob and releases the microphone track', async () => {
    FakeMediaRecorder.supportedTypes = new Set(['audio/webm'])
    const recorder = new BrowserAudioRecorder()

    await recorder.start()
    expect(recorder.isRecording).toBe(true)

    const audio = await recorder.stop()

    expect(audio.type).toBe('audio/webm')
    expect(await audio.text()).toBe('recorded sermon')
    expect(recorder.isRecording).toBe(false)
    expect(stopTrack).toHaveBeenCalledOnce()
  })

  it('uses timeslices for WebM but not for MP4', async () => {
    FakeMediaRecorder.supportedTypes = new Set(['audio/webm'])
    const webmRecorder = new BrowserAudioRecorder()
    await webmRecorder.start()
    const webmMedia = (webmRecorder as unknown as { mediaRecorder: FakeMediaRecorder })
      .mediaRecorder
    expect(webmMedia.startTimeslice).toBe(1_000)
    await webmRecorder.stop()

    FakeMediaRecorder.supportedTypes = new Set(['audio/mp4'])
    const mp4Recorder = new BrowserAudioRecorder()
    await mp4Recorder.start()
    const mp4Media = (mp4Recorder as unknown as { mediaRecorder: FakeMediaRecorder })
      .mediaRecorder
    expect(mp4Media.startTimeslice).toBeUndefined()
    await mp4Recorder.stop()
  })

  it('reports support when microphone and MediaRecorder APIs exist', () => {
    expect(supportsAudioRecording()).toBe(true)
  })

  it('preserves microphone permission errors from the browser', async () => {
    getUserMedia.mockRejectedValueOnce(
      new DOMException('Permission denied', 'NotAllowedError'),
    )
    const recorder = new BrowserAudioRecorder()

    await expect(recorder.start()).rejects.toMatchObject({
      name: 'NotAllowedError',
    })
  })
})
