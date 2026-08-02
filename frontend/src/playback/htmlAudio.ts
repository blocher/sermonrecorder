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
