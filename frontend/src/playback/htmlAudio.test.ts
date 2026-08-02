import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  isHtmlAudioAbortError,
  playHtmlAudio,
  waitForHtmlAudioCanPlay,
} from './htmlAudio'

function fakeAudio(readyState = 0) {
  const listeners = new Map<string, Set<EventListener>>()
  const element = {
    readyState,
    currentTime: 0,
    networkState: 0,
    error: null as MediaError | null,
    load: vi.fn(function load(this: { currentTime: number; networkState: number }) {
      // HTMLMediaElement.load() resets playback position.
      this.currentTime = 0
      this.networkState = 2
    }),
    play: vi.fn(async () => undefined),
    addEventListener: vi.fn((type: string, listener: EventListener) => {
      const set = listeners.get(type) ?? new Set()
      set.add(listener)
      listeners.set(type, set)
    }),
    removeEventListener: vi.fn((type: string, listener: EventListener) => {
      listeners.get(type)?.delete(listener)
    }),
    emit(type: string) {
      for (const listener of listeners.get(type) ?? []) {
        listener(new Event(type))
      }
    },
  }
  return element
}

describe('htmlAudio', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('detects AbortError from play interruptions', () => {
    expect(isHtmlAudioAbortError(new DOMException('interrupted', 'AbortError'))).toBe(true)
    expect(isHtmlAudioAbortError(new Error('nope'))).toBe(false)
  })

  it('resolves immediately when the element already has current data', async () => {
    const element = fakeAudio(2)
    await waitForHtmlAudioCanPlay(element as unknown as HTMLAudioElement)
    expect(element.load).not.toHaveBeenCalled()
  })

  it('loads and waits for canplay when the element is cold', async () => {
    const element = fakeAudio(0)
    const pending = waitForHtmlAudioCanPlay(element as unknown as HTMLAudioElement)
    expect(element.load).toHaveBeenCalledOnce()
    element.emit('canplay')
    await pending
  })

  it('plays immediately when ready', async () => {
    const element = fakeAudio(2)
    await playHtmlAudio(element as unknown as HTMLAudioElement)
    expect(element.play).toHaveBeenCalledOnce()
    expect(element.load).not.toHaveBeenCalled()
  })

  it('retries after canplay when the first play loses a readiness race', async () => {
    const element = fakeAudio(0)
    element.play
      .mockRejectedValueOnce(new DOMException('not ready', 'NotSupportedError'))
      .mockResolvedValueOnce(undefined)

    const pending = playHtmlAudio(element as unknown as HTMLAudioElement)
    await vi.waitFor(() => {
      expect(element.addEventListener).toHaveBeenCalledWith(
        'canplay',
        expect.any(Function),
        expect.anything(),
      )
    })
    element.emit('canplay')
    await pending

    expect(element.load).toHaveBeenCalled()
    expect(element.play).toHaveBeenCalledTimes(2)
  })

  it('keeps a prior seek when load is required before play', async () => {
    const element = fakeAudio(1) // HAVE_METADATA after preload="metadata"
    element.currentTime = 125

    const pending = playHtmlAudio(element as unknown as HTMLAudioElement)
    element.emit('loadedmetadata')
    element.emit('canplay')
    await pending

    expect(element.load).toHaveBeenCalledOnce()
    expect(element.currentTime).toBe(125)
    expect(element.play).toHaveBeenCalled()
  })
})
