import type {
  SnapshotEnvelope,
  WorkerRequest,
  WorkerResponse,
} from './protocol'
import { isSnapshotEnvelope } from './snapshot-store'

export interface SnapshotStore {
  load(): Promise<unknown | undefined>
  save(snapshot: SnapshotEnvelope): Promise<void>
  clear(): Promise<void>
}

type WorkerRequester = (request: WorkerRequest) => Promise<WorkerResponse>

export class StoredSnapshotError extends Error {
  constructor(message: string) {
    super(`Stored clinic state cannot be restored: ${message}`)
    this.name = 'StoredSnapshotError'
  }
}

/** Coordinates worker requests with durable browser snapshot storage. */
export class PersistentWorkerSession {
  readonly #requestWorker: WorkerRequester
  readonly #store: SnapshotStore

  constructor(requestWorker: WorkerRequester, store: SnapshotStore) {
    this.#requestWorker = requestWorker
    this.#store = store
  }

  async initialize(id: string): Promise<WorkerResponse> {
    const snapshot = await this.#store.load()
    if (snapshot !== undefined && !isSnapshotEnvelope(snapshot))
      throw new StoredSnapshotError('the saved value is corrupt; reset the sandbox to continue')

    const response = await this.#requestWorker({
      id,
      operation: 'initialize',
      ...(snapshot === undefined ? {} : { snapshot }),
    })
    if (!response.ok && snapshot !== undefined)
      throw new StoredSnapshotError(`${response.error.message}; reset the sandbox to continue`)
    return response
  }

  async request(request: WorkerRequest): Promise<WorkerResponse> {
    if (request.operation === 'initialize')
      return this.initialize(request.id)

    const response = await this.#requestWorker(request)
    if (!response.ok)
      return response

    if (request.operation === 'reset') {
      await this.#store.clear()
      return response
    }

    if (request.operation === 'execute' || request.operation === 'seed') {
      if (!isSnapshotEnvelope(response.snapshot))
        throw new Error(`WASM ${request.operation} response did not include a valid snapshot`)
      await this.#store.save(response.snapshot)
    }

    return response
  }

  /** Clear an unreadable snapshot and reset the in-memory runtime. */
  async recoverByReset(id: string): Promise<WorkerResponse> {
    const response = await this.#requestWorker({ id, operation: 'reset' })
    if (response.ok)
      await this.#store.clear()
    return response
  }
}
