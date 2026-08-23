import { ApiError } from '../api/runtime-contract'
import type { RuntimeRequest, ShowcaseRuntime } from '../api/runtime-contract'
import { PersistentWorkerSession } from './persistent-session'
import type { SnapshotStore } from './persistent-session'
import type { RuntimeErrorCategory, WorkerRequest, WorkerResponse } from './protocol'
import { ClinicSnapshotStore } from './snapshot-store'

type WorkerFactory = () => Worker
type IdFactory = () => string

const STATUS_BY_CATEGORY: Record<RuntimeErrorCategory, number> = {
  bad_request: 400,
  not_found: 404,
  conflict: 409,
  validation: 422,
  internal: 500,
}

function createRuntimeWorker(): Worker {
  return new Worker(new URL('./runtime.worker.ts', import.meta.url), { type: 'module' })
}

function sequentialIds(): IdFactory {
  let sequence = 0
  return () => `showcase-${++sequence}`
}

function assertWorkerResponse(value: unknown): asserts value is WorkerResponse {
  if (
    typeof value !== 'object'
    || value === null
    || typeof (value as Record<string, unknown>).id !== 'string'
    || typeof (value as Record<string, unknown>).ok !== 'boolean'
  ) {
    throw new Error('WASM worker returned an invalid response envelope')
  }
}

class WorkerTransport {
  readonly #worker: Worker
  readonly #pending = new Map<string, {
    resolve: (response: WorkerResponse) => void
    reject: (error: Error) => void
  }>()

  constructor(worker: Worker) {
    this.#worker = worker
    worker.addEventListener('message', (event: MessageEvent<unknown>) => {
      try {
        assertWorkerResponse(event.data)
        const pending = this.#pending.get(event.data.id)
        if (!pending)
          return
        this.#pending.delete(event.data.id)
        pending.resolve(event.data)
      }
      catch (error) {
        this.#rejectAll(error instanceof Error ? error : new Error(String(error)))
      }
    })
    worker.addEventListener('error', (event) => {
      this.#rejectAll(new Error(event.message || 'WASM worker failed'))
    })
  }

  request(request: WorkerRequest): Promise<WorkerResponse> {
    if (this.#pending.has(request.id))
      return Promise.reject(new Error(`Duplicate WASM worker request id '${request.id}'`))

    return new Promise((resolve, reject) => {
      this.#pending.set(request.id, { resolve, reject })
      try {
        this.#worker.postMessage(request)
      }
      catch (error) {
        this.#pending.delete(request.id)
        reject(error instanceof Error ? error : new Error(String(error)))
      }
    })
  }

  terminate(): void {
    this.#rejectAll(new Error('WASM worker was terminated'))
    this.#worker.terminate()
  }

  #rejectAll(error: Error): void {
    for (const pending of this.#pending.values())
      pending.reject(error)
    this.#pending.clear()
  }
}

/** Runtime-neutral client backed exclusively by the Rust WASM worker. */
export class WasmShowcaseRuntime implements ShowcaseRuntime {
  readonly #session: PersistentWorkerSession
  readonly #transport: WorkerTransport
  readonly #nextId: IdFactory
  #initialized: Promise<void> | undefined

  constructor(
    createWorker: WorkerFactory = createRuntimeWorker,
    store: SnapshotStore = new ClinicSnapshotStore(),
    nextId: IdFactory = sequentialIds(),
  ) {
    this.#transport = new WorkerTransport(createWorker())
    this.#session = new PersistentWorkerSession(
      request => this.#transport.request(request),
      store,
    )
    this.#nextId = nextId
  }

  async request<T>(request: RuntimeRequest): Promise<T> {
    await this.#initialize()
    const response = await this.#session.request({
      id: this.#nextId(),
      operation: request.method === 'GET' ? 'query' : 'execute',
      payload: request,
    })
    return this.#result<T>(response)
  }

  terminate(): void {
    this.#transport.terminate()
  }

  #initialize(): Promise<void> {
    this.#initialized ??= this.#session.initialize(this.#nextId()).then((response) => {
      this.#result(response)
    })
    return this.#initialized
  }

  #result<T>(response: WorkerResponse): T {
    if (response.ok)
      return response.result as T
    throw new ApiError(STATUS_BY_CATEGORY[response.error.category], {
      error: response.error.message,
      category: response.error.category,
    })
  }
}
