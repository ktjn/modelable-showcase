import { ApiError } from '../api/runtime-contract'
import type { RuntimeInfo, RuntimeRequest, ShowcaseRuntime } from '../api/runtime-contract'
import { PersistentWorkerSession } from './persistent-session'
import type { SnapshotStore } from './persistent-session'
import { MAX_SNAPSHOT_BYTES } from './protocol'
import type { RuntimeErrorCategory, SnapshotEnvelope, WorkerRequest, WorkerResponse } from './protocol'
import { ClinicSnapshotStore, isSnapshotEnvelope } from './snapshot-store'

type WorkerFactory = () => Worker
type IdFactory = () => string

interface WasmEngineInfo {
  modelableVersion: string
  schemaIdentity: string
}

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
  readonly kind = 'wasm' as const
  readonly #session: PersistentWorkerSession
  readonly #transport: WorkerTransport
  readonly #nextId: IdFactory
  readonly #seedOnFirstVisit: boolean
  #initialized: Promise<WasmEngineInfo> | undefined

  constructor(
    createWorker: WorkerFactory = createRuntimeWorker,
    store: SnapshotStore = new ClinicSnapshotStore(),
    nextId: IdFactory = sequentialIds(),
    seedOnFirstVisit = import.meta.env.VITE_SHOWCASE_STATIC === 'true',
  ) {
    this.#transport = new WorkerTransport(createWorker())
    this.#session = new PersistentWorkerSession(
      request => this.#transport.request(request),
      store,
    )
    this.#nextId = nextId
    this.#seedOnFirstVisit = seedOnFirstVisit
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

  async info(): Promise<RuntimeInfo> {
    const info = await this.#initialize()
    return {
      runtime: 'Rust / WebAssembly',
      modelableVersion: info.modelableVersion,
      schemaIdentity: info.schemaIdentity,
      storage: 'IndexedDB',
    }
  }

  async seed<T = unknown>(): Promise<T> {
    await this.#initialize()
    return this.#result<T>(await this.#session.request({
      id: this.#nextId(),
      operation: 'seed',
    }))
  }

  async reset<T = unknown>(): Promise<T> {
    await this.#initialize()
    return this.#result<T>(await this.#session.request({
      id: this.#nextId(),
      operation: 'reset',
    }))
  }

  async snapshot(): Promise<SnapshotEnvelope> {
    await this.#initialize()
    const snapshot = this.#result<unknown>(await this.#session.request({
      id: this.#nextId(),
      operation: 'snapshot',
    }))
    if (!isSnapshotEnvelope(snapshot))
      throw new Error('WASM runtime returned an invalid clinic snapshot')
    return snapshot
  }

  async restore(snapshot: unknown): Promise<void> {
    if (!isSnapshotEnvelope(snapshot))
      throw new Error('The selected file is not a valid clinic snapshot')
    if (new TextEncoder().encode(JSON.stringify(snapshot)).byteLength > MAX_SNAPSHOT_BYTES)
      throw new Error('The selected clinic snapshot exceeds the 2 MiB limit')
    await this.#initialize()
    this.#result(await this.#session.request({
      id: this.#nextId(),
      operation: 'restore',
      snapshot,
    }))
  }

  terminate(): void {
    this.#transport.terminate()
  }

  #initialize(): Promise<WasmEngineInfo> {
    this.#initialized ??= this.#session.initialize(
      this.#nextId(),
      this.#seedOnFirstVisit ? this.#nextId() : undefined,
    ).then(response => (
      this.#result<WasmEngineInfo>(response)
    ))
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
