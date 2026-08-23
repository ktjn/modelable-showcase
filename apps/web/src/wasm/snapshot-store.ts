import type { SnapshotEnvelope } from './protocol'

const DATABASE_NAME = 'modelable-showcase-wasm'
const DATABASE_VERSION = 1
const STORE_NAME = 'snapshots'
const CLINIC_STATE_KEY = 'clinic-state'

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'))
  })
}

function transactionComplete(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB transaction aborted'))
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
  })
}

export function isSnapshotEnvelope(value: unknown): value is SnapshotEnvelope {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    return false

  const candidate = value as Record<string, unknown>
  return Number.isInteger(candidate.formatVersion)
    && typeof candidate.modelableVersion === 'string'
    && typeof candidate.schemaIdentity === 'string'
    && typeof candidate.state === 'object'
    && candidate.state !== null
    && !Array.isArray(candidate.state)
}

/** Minimal IndexedDB persistence for the browser clinic snapshot. */
export class ClinicSnapshotStore {
  readonly #factory: IDBFactory
  readonly #databaseName: string
  #databasePromise: Promise<IDBDatabase> | undefined

  constructor(factory: IDBFactory = globalThis.indexedDB, databaseName = DATABASE_NAME) {
    this.#factory = factory
    this.#databaseName = databaseName
  }

  async load(): Promise<unknown | undefined> {
    const database = await this.#database()
    const transaction = database.transaction(STORE_NAME, 'readonly')
    const completed = transactionComplete(transaction)
    const value = await requestResult(transaction.objectStore(STORE_NAME).get(CLINIC_STATE_KEY))
    await completed
    return value
  }

  async save(snapshot: SnapshotEnvelope): Promise<void> {
    const database = await this.#database()
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const completed = transactionComplete(transaction)
    transaction.objectStore(STORE_NAME).put(snapshot, CLINIC_STATE_KEY)
    await completed
  }

  async clear(): Promise<void> {
    const database = await this.#database()
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const completed = transactionComplete(transaction)
    transaction.objectStore(STORE_NAME).delete(CLINIC_STATE_KEY)
    await completed
  }

  async close(): Promise<void> {
    const databasePromise = this.#databasePromise
    this.#databasePromise = undefined
    if (databasePromise)
      (await databasePromise).close()
  }

  #database(): Promise<IDBDatabase> {
    this.#databasePromise ??= new Promise((resolve, reject) => {
      const request = this.#factory.open(this.#databaseName, DATABASE_VERSION)
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE_NAME))
          request.result.createObjectStore(STORE_NAME)
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error ?? new Error('Could not open clinic storage'))
      request.onblocked = () => reject(new Error('Clinic storage upgrade is blocked by another tab'))
    })
    return this.#databasePromise
  }
}
