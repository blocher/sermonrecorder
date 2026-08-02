/** HAVE_CURRENT_DATA — enough buffered to begin playback. */
const HAVE_CURRENT_DATA = 2

/** True when a media play/load was interrupted by a newer load or pause. */
export function isHtmlAudioAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
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
    element.load()
  })
}

/**
 * Start playback on mobile-safe terms: kick a load when the element is cold,
 * prefer an immediate play() while user activation is fresh, then retry once
 * after canplay if the first attempt lost a readiness race.
 */
export async function playHtmlAudio(element: HTMLAudioElement): Promise<void> {
  if (element.readyState >= HAVE_CURRENT_DATA) {
    await element.play()
    return
  }

  // Start fetching under the current gesture; iOS ignores preload until then.
  element.load()

  try {
    await element.play()
    return
  } catch (error) {
    if (isHtmlAudioAbortError(error)) return
    if (element.error) throw error
  }

  await waitForHtmlAudioCanPlay(element)
  await element.play()
}
