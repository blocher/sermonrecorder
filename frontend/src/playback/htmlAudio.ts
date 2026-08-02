/** HAVE_METADATA — duration and dimensions are known; seeking is allowed. */
const HAVE_METADATA = 1
/** HAVE_CURRENT_DATA — enough buffered to begin playback. */
const HAVE_CURRENT_DATA = 2
/** NETWORK_LOADING — the user agent is actively fetching. */
const NETWORK_LOADING = 2

/** True when a media play/load was interrupted by a newer load or pause. */
export function isHtmlAudioAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function describeHtmlAudioError(element: HTMLAudioElement): string {
  const code = element.error?.code ?? 0
  const label =
    {
      1: 'Playback was aborted',
      2: 'A network error interrupted audio',
      3: 'The audio could not be decoded',
      4: 'This audio source is not supported',
    }[code] ?? 'The audio element failed'
  return `${label} (media ${code}, ready ${element.readyState}, network ${element.networkState})`
}

function restoreCurrentTime(element: HTMLAudioElement, seconds: number): void {
  if (!(seconds > 0) || !Number.isFinite(seconds)) return
  if (Math.abs(element.currentTime - seconds) < 0.05) return
  element.currentTime = seconds
}

/** Wait until the element can begin playback, forcing a load when needed (iOS). */
export async function waitForHtmlAudioCanPlay(element: HTMLAudioElement): Promise<void> {
  if (element.readyState >= HAVE_CURRENT_DATA) return

  await new Promise<void>((resolve, reject) => {
    const onReady = () => {
      cleanup()
      resolve()
    }
    const onError = () => {
      cleanup()
      reject(new Error('This recording could not be loaded.'))
    }
    const cleanup = () => {
      element.removeEventListener('canplay', onReady)
      element.removeEventListener('error', onError)
    }
    element.addEventListener('canplay', onReady, { once: true })
    element.addEventListener('error', onError, { once: true })
    // Avoid a second load() when playHtmlAudio already kicked one off — load()
    // resets currentTime and would wipe a seek we are about to restore.
    if (element.networkState !== NETWORK_LOADING) {
      element.load()
    }
  })
}

/**
 * Download a remote media source and prepare it as a local Blob URL.
 *
 * iOS WebKit can reject an otherwise valid ranged M4A URL before decoding it
 * (MEDIA_ERR_SRC_NOT_SUPPORTED). A local Blob bypasses that remote media loader
 * while preserving the same authenticated/capability URL and audio bytes.
 */
export async function prepareHtmlAudioBlobFallback(
  element: HTMLAudioElement,
  sourceUrl: string,
): Promise<string> {
  const response = await fetch(sourceUrl, {
    cache: 'no-store',
    credentials: 'omit',
    mode: 'cors',
  })
  if (!response.ok) {
    throw new Error(`Audio download failed (${response.status}).`)
  }

  const downloaded = await response.blob()
  if (!downloaded.size) {
    throw new Error('Audio download was empty.')
  }
  const contentType =
    downloaded.type || response.headers.get('content-type')?.split(';')[0] || 'audio/mp4'
  const blob =
    downloaded.type === contentType
      ? downloaded
      : new Blob([downloaded], { type: contentType })
  const objectUrl = URL.createObjectURL(blob)

  element.src = objectUrl
  element.load()
  try {
    await waitForHtmlAudioCanPlay(element)
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    throw error
  }
  return objectUrl
}

/**
 * Start playback on mobile-safe terms: kick a load when the element is cold,
 * prefer an immediate play() while user activation is fresh, then retry once
 * after canplay if the first attempt lost a readiness race.
 *
 * Preserves currentTime across load(), so seek-then-play (timestamp taps,
 * scrubbing) does not restart from the beginning when only metadata is ready.
 */
export async function playHtmlAudio(element: HTMLAudioElement): Promise<void> {
  const resumeAt = element.currentTime

  if (element.readyState >= HAVE_CURRENT_DATA) {
    await element.play()
    return
  }

  // Start fetching under the current gesture; iOS ignores preload until then.
  // load() resets currentTime — restore after metadata / before retries.
  element.addEventListener(
    'loadedmetadata',
    () => restoreCurrentTime(element, resumeAt),
    { once: true },
  )
  element.load()
  if (element.readyState >= HAVE_METADATA) {
    restoreCurrentTime(element, resumeAt)
  }

  try {
    await element.play()
    restoreCurrentTime(element, resumeAt)
    return
  } catch (error) {
    if (isHtmlAudioAbortError(error)) return
    if (element.error) throw error
  }

  await waitForHtmlAudioCanPlay(element)
  restoreCurrentTime(element, resumeAt)
  await element.play()
}
