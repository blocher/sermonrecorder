const DATABASE_NAME = 'pewcorder'
const DATABASE_VERSION = 1
const DRAFT_STORE = 'drafts'

export interface LocalDraft {
  id: string
  createdAt: string
  durationSeconds: number
  mimeType: string
  sizeBytes: number
  audio: Blob
}

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
  audio: Blob,
  durationSeconds: number,
  createdAt = new Date(),
): Promise<LocalDraft> {
  if (audio.size === 0) throw new Error('The recording contains no audio.')

  const draft: LocalDraft = {
    id: draftId(),
    createdAt: createdAt.toISOString(),
    durationSeconds: Math.max(1, Math.round(durationSeconds)),
    mimeType: audio.type || 'audio/webm',
    sizeBytes: audio.size,
    audio,
  }

  const database = await openDatabase()
  const transaction = database.transaction(DRAFT_STORE, 'readwrite')
  transaction.objectStore(DRAFT_STORE).put(draft)
  await transactionComplete(transaction)
  return draft
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
