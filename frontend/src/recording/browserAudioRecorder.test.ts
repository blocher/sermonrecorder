import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserAudioRecorder, supportsAudioRecording } from './browserAudioRecorder'

class FakeMediaRecorder extends EventTarget {
  static isTypeSupported(type: string): boolean {
    return type === 'audio/webm'
  }

  readonly mimeType: string
  state: RecordingState = 'inactive'

  constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
    super()
    this.mimeType = options?.mimeType ?? 'audio/webm'
  }

  start(): void {
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
  it('captures an audio Blob and releases the microphone track', async () => {
    const recorder = new BrowserAudioRecorder()

    await recorder.start()
    expect(recorder.isRecording).toBe(true)

    const audio = await recorder.stop()

    expect(audio.type).toBe('audio/webm')
    expect(await audio.text()).toBe('recorded sermon')
    expect(recorder.isRecording).toBe(false)
    expect(stopTrack).toHaveBeenCalledOnce()
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
