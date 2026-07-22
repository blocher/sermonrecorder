import { deleteNativeDraftFile, persistNativeRecording } from './nativeDraftFiles'
import type { OccasionKind } from '../sermons/serverSermon'

const DATABASE_NAME = 'pewcorder'
const DATABASE_VERSION = 2
const DRAFT_STORE = 'drafts'

export interface NativeAudioFile {
  kind: 'native-file'
  uri: string
  mimeType: string
}

export type DraftAudioInput = Blob | NativeAudioFile

export type DraftLocationStatus = 'pending' | 'captured' | 'denied' | 'unavailable'

export interface LocalDraft {
  id: string
  createdAt: string
  durationSeconds: number
  mimeType: string
  sizeBytes: number
  audio?: Blob
  audioPath?: string
  latitude?: number
  longitude?: number
  locationStatus?: DraftLocationStatus
  churchId?: string
  churchName?: string
  churchAddress?: string
  churchLatitude?: number
  churchLongitude?: number
  preacherId?: string
  preacherName?: string
  occasionKind?: OccasionKind | ''
  liturgicalDay?: string
}

export type LocalDraftMetadataPatch = Partial<
  Pick<
    LocalDraft,
    | 'latitude'
    | 'longitude'
    | 'locationStatus'
    | 'churchId'
    | 'churchName'
    | 'churchAddress'
    | 'churchLatitude'
    | 'churchLongitude'
    | 'preacherId'
    | 'preacherName'
    | 'occasionKind'
    | 'liturgicalDay'
  >
>

let databasePromise: Promise<IDBDatabase> | undefined

function openDatabase(): Promise<IDBDatabase> {
  if (databasePromise) return databasePromise

  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)

    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(DRAFT_STORE)) {
        const store = database.createObjectStore(DRAFT_STORE, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt')
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => {
      databasePromise = undefined
      reject(request.error ?? new Error('Could not open local Draft storage.'))
    }
  })

  return databasePromise
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('A local Draft operation failed.'))
  })
}

function transactionComplete(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onerror = () =>
      reject(transaction.error ?? new Error('A local Draft transaction failed.'))
    transaction.onabort = () =>
      reject(transaction.error ?? new Error('A local Draft transaction was cancelled.'))
  })
}

function draftId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `draft-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export async function createDraft(
  audio: DraftAudioInput,
  durationSeconds: number,
  createdAt = new Date(),
): Promise<LocalDraft> {
  const id = draftId()
  let nativeAudioPath: string | undefined
  let draft: LocalDraft

  if (audio instanceof Blob) {
    if (audio.size === 0) throw new Error('The recording contains no audio.')
    draft = {
      id,
      createdAt: createdAt.toISOString(),
      durationSeconds: Math.max(1, Math.round(durationSeconds)),
      mimeType: audio.type || 'audio/webm',
      sizeBytes: audio.size,
      audio,
      locationStatus: 'pending',
    }
  } else {
    const persistedAudio = await persistNativeRecording(audio.uri, id)
    nativeAudioPath = persistedAudio.path
    if (persistedAudio.sizeBytes === 0) {
      await deleteNativeDraftFile(persistedAudio.path)
      throw new Error('The recording contains no audio.')
    }

    draft = {
      id,
      createdAt: createdAt.toISOString(),
      durationSeconds: Math.max(1, Math.round(durationSeconds)),
      mimeType: audio.mimeType,
      sizeBytes: persistedAudio.sizeBytes,
      audioPath: persistedAudio.path,
      locationStatus: 'pending',
    }
  }

  const database = await openDatabase()
  const transaction = database.transaction(DRAFT_STORE, 'readwrite')
  transaction.objectStore(DRAFT_STORE).put(draft)

  try {
    await transactionComplete(transaction)
  } catch (error) {
    if (nativeAudioPath) await deleteNativeDraftFile(nativeAudioPath).catch(() => undefined)
    throw error
  }

  return draft
}

export async function getDraft(id: string): Promise<LocalDraft | undefined> {
  const database = await openDatabase()
  const transaction = database.transaction(DRAFT_STORE, 'readonly')
  const draft = await requestResult<LocalDraft | undefined>(
    transaction.objectStore(DRAFT_STORE).get(id),
  )
  await transactionComplete(transaction)
  return draft
}

export async function updateDraft(
  id: string,
  patch: LocalDraftMetadataPatch,
): Promise<LocalDraft> {
  const database = await openDatabase()
  const transaction = database.transaction(DRAFT_STORE, 'readwrite')
  const store = transaction.objectStore(DRAFT_STORE)
  const existing = await requestResult<LocalDraft | undefined>(store.get(id))
  if (!existing) {
    transaction.abort()
    throw new Error('That Draft is no longer on this device.')
  }

  const updated: LocalDraft = { ...existing, ...patch }
  store.put(updated)
  await transactionComplete(transaction)
  return updated
}

export async function listDrafts(): Promise<LocalDraft[]> {
  const database = await openDatabase()
  const transaction = database.transaction(DRAFT_STORE, 'readonly')
  const drafts = await requestResult<LocalDraft[]>(transaction.objectStore(DRAFT_STORE).getAll())
  await transactionComplete(transaction)
  return drafts.sort((left, right) => right.createdAt.localeCompare(left.createdAt))
}

export async function deleteDraft(id: string): Promise<void> {
  const database = await openDatabase()
  const readTransaction = database.transaction(DRAFT_STORE, 'readonly')
  const draft = await requestResult<LocalDraft | undefined>(
    readTransaction.objectStore(DRAFT_STORE).get(id),
  )
  await transactionComplete(readTransaction)

  if (draft?.audioPath) {
    await deleteNativeDraftFile(draft.audioPath).catch(() => undefined)
  }

  const transaction = database.transaction(DRAFT_STORE, 'readwrite')
  transaction.objectStore(DRAFT_STORE).delete(id)
  await transactionComplete(transaction)
}

export async function closeDraftDatabase(): Promise<void> {
  const activeDatabase = databasePromise
  databasePromise = undefined
  if (!activeDatabase) return
  const database = await activeDatabase
  database.close()
}
