import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  describeHtmlAudioError,
  isHtmlAudioAbortError,
  playHtmlAudio,
  prepareHtmlAudioBlobFallback,
  seekHtmlAudio,
  waitForHtmlAudioCanPlay,
} from './htmlAudio'

function fakeAudio(readyState = 0) {
  const listeners = new Map<string, Set<EventListener>>()
  const element = {
    readyState,
    currentTime: 0,
    src: '',
    networkState: 0,
    error: null as MediaError | null,
    load: vi.fn(function load(this: {
      currentTime: number
      networkState: number
      readyState: number
    }) {
      // HTMLMediaElement.load() resets playback position.
      this.currentTime = 0
      this.networkState = 2
      this.readyState = 0
    }),
    play: vi.fn(async () => undefined),
    pause: vi.fn(),
    addEventListener: vi.fn((type: string, listener: EventListener) => {
      const set = listeners.get(type) ?? new Set()
      set.add(listener)
      listeners.set(type, set)
    }),
    removeEventListener: vi.fn((type: string, listener: EventListener) => {
      listeners.get(type)?.delete(listener)
    }),
    emit(type: string) {
      if (type === 'loadedmetadata' && element.readyState < 1) element.readyState = 1
      if (type === 'canplay' && element.readyState < 2) element.readyState = 2
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

  it('describes media failures with browser state', () => {
    const element = fakeAudio(0)
    element.networkState = 3
    element.error = { code: 4 } as MediaError

    expect(describeHtmlAudioError(element as unknown as HTMLAudioElement)).toBe(
      'This audio source is not supported (media 4, ready 0, network 3)',
    )
  })

  it('downloads rejected remote audio and prepares a local Blob URL', async () => {
    const element = fakeAudio(0)
    const objectUrl = 'blob:https://pewcorder.test/mobile-audio'
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(new Blob(['audio'], { type: 'audio/mp4' }))),
    )
    vi.spyOn(URL, 'createObjectURL').mockReturnValue(objectUrl)

    const pending = prepareHtmlAudioBlobFallback(
      element as unknown as HTMLAudioElement,
      'https://api.example.test/audio/',
    )
    await vi.waitFor(() => expect(element.src).toBe(objectUrl))
    element.emit('canplay')

    await expect(pending).resolves.toBe(objectUrl)
    expect(fetch).toHaveBeenCalledWith('https://api.example.test/audio/', {
      cache: 'no-store',
      credentials: 'omit',
      mode: 'cors',
    })
    expect(element.load).toHaveBeenCalledOnce()
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

  it('retries after canplay when load() aborts the first play attempt', async () => {
    const element = fakeAudio(0)
    element.play
      .mockRejectedValueOnce(new DOMException('The operation was aborted.', 'AbortError'))
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

    expect(element.play).toHaveBeenCalledTimes(2)
  })

  it('seeks to an explicit resumeAt when the element was just remounted at 0', async () => {
    const element = fakeAudio(0)
    element.currentTime = 0

    const pending = playHtmlAudio(element as unknown as HTMLAudioElement, { resumeAt: 182 })
    element.emit('loadedmetadata')
    element.emit('canplay')
    element.emit('seeked')
    await pending

    expect(element.currentTime).toBe(182)
    expect(element.play).toHaveBeenCalled()
  })

  it('does not resume play after the caller pauses mid-load', async () => {
    const element = fakeAudio(0)
    element.play
      .mockRejectedValueOnce(new DOMException('not ready', 'NotSupportedError'))
      .mockResolvedValueOnce(undefined)
    const session = { cancelled: false }

    const pending = playHtmlAudio(element as unknown as HTMLAudioElement, { session })
    await vi.waitFor(() => {
      expect(element.addEventListener).toHaveBeenCalledWith(
        'canplay',
        expect.any(Function),
        expect.anything(),
      )
    })
    session.cancelled = true
    element.emit('canplay')
    await pending

    expect(element.play).toHaveBeenCalledTimes(1)
  })

  it('waits for seeked when jumping to an unbuffered position', async () => {
    const element = fakeAudio(2)
    element.currentTime = 10

    const pending = seekHtmlAudio(element as unknown as HTMLAudioElement, 240, {
      timeoutMs: 1000,
    })
    await vi.waitFor(() => expect(element.currentTime).toBe(240))
    element.emit('seeked')
    await pending
    expect(element.currentTime).toBe(240)
  })
})
