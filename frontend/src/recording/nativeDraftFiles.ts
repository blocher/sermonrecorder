import { Capacitor } from '@capacitor/core'
import { Directory, Filesystem } from '@capacitor/filesystem'

const DRAFT_DIRECTORY = 'drafts'
const DRAFT_STORAGE = Directory.LibraryNoCloud

let draftDirectoryPromise: Promise<void> | undefined

async function ensureDraftDirectory(): Promise<void> {
  if (!draftDirectoryPromise) {
    draftDirectoryPromise = Filesystem.mkdir({
      path: DRAFT_DIRECTORY,
      directory: DRAFT_STORAGE,
      recursive: true,
    }).catch(async (error: unknown) => {
      try {
        await Filesystem.readdir({ path: DRAFT_DIRECTORY, directory: DRAFT_STORAGE })
      } catch {
        draftDirectoryPromise = undefined
        throw error
      }
    })
  }

  await draftDirectoryPromise
}

export async function persistNativeRecording(
  sourceUri: string,
  draftId: string,
): Promise<{ path: string; sizeBytes: number }> {
  await ensureDraftDirectory()
  const path = `${DRAFT_DIRECTORY}/${draftId}.m4a`

  await Filesystem.copy({
    from: sourceUri,
    to: path,
    toDirectory: DRAFT_STORAGE,
  })

  const { size } = await Filesystem.stat({ path, directory: DRAFT_STORAGE })

  try {
    await Filesystem.deleteFile({ path: sourceUri })
  } catch {
    // The captured source lives in a temporary/cache directory and may already be gone.
  }

  return { path, sizeBytes: size }
}

export async function deleteNativeDraftFile(path: string): Promise<void> {
  await Filesystem.deleteFile({ path, directory: DRAFT_STORAGE })
}

export async function nativeDraftPlaybackUrl(path: string): Promise<string> {
  return Capacitor.convertFileSrc(await nativeDraftFileUri(path))
}

export async function nativeDraftFileUri(path: string): Promise<string> {
  const { uri } = await Filesystem.getUri({ path, directory: DRAFT_STORAGE })
  return uri
}
