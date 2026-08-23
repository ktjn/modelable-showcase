import type {
  RuntimeError,
  RuntimeErrorCategory,
  WorkerFailure,
  WorkerRequest,
  WorkerResponse,
  WorkerSuccess,
} from './protocol'
import { dispatchRoute, isRuntimeRequest, RouteDispatchError } from './route-adapter'

export interface WasmRuntime {
  initialize(snapshotJson?: string | null): string
  execute(commandJson: string): string
  query(queryJson: string): string
  snapshot(): string
  reset(): string
  seed(): string
}

interface RuntimeSuccess {
  ok: true
  result: unknown
}

interface RuntimeFailure {
  ok: false
  error: RuntimeError
}

type RuntimeResponse = RuntimeSuccess | RuntimeFailure
type RuntimeLoader = () => Promise<WasmRuntime>
type Clock = () => string
type IdFactory = () => string

const ERROR_CATEGORIES = new Set<RuntimeErrorCategory>([
  'bad_request',
  'not_found',
  'conflict',
  'validation',
  'internal',
])
const OPERATIONS = new Set(['initialize', 'execute', 'query', 'snapshot', 'reset', 'seed'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseRuntimeResponse(json: string): RuntimeResponse {
  let response: unknown
  try {
    response = JSON.parse(json)
  }
  catch (error) {
    throw new Error(`WASM runtime returned invalid JSON: ${errorMessage(error)}`)
  }
  if (!isRecord(response) || typeof response.ok !== 'boolean') {
    throw new Error('WASM runtime returned an invalid response envelope')
  }
  if (response.ok) {
    return { ok: true, result: response.result }
  }
  if (!isRecord(response.error)) {
    throw new Error('WASM runtime returned an invalid error envelope')
  }
  const category = response.error.category
  const message = response.error.message
  if (
    typeof category !== 'string'
    || !ERROR_CATEGORIES.has(category as RuntimeErrorCategory)
    || typeof message !== 'string'
  ) {
    throw new Error('WASM runtime returned an invalid error envelope')
  }
  return { ok: false, error: { category: category as RuntimeErrorCategory, message } }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function failure(id: string, category: RuntimeErrorCategory, message: string): WorkerFailure {
  return { id, ok: false, error: { category, message } }
}

function success(id: string, result: unknown, snapshot?: unknown): WorkerSuccess {
  return snapshot === undefined
    ? { id, ok: true, result }
    : { id, ok: true, result, snapshot }
}

/** Serial request processor around one lazily loaded WASM runtime instance. */
export class WorkerRuntimeHost {
  readonly #loadRuntime: RuntimeLoader
  readonly #clock: Clock
  readonly #newId: IdFactory
  #runtimePromise: Promise<WasmRuntime> | undefined
  #queue: Promise<void> = Promise.resolve()

  constructor(
    loadRuntime: RuntimeLoader,
    clock: Clock = () => new Date().toISOString(),
    newId: IdFactory = () => crypto.randomUUID(),
  ) {
    this.#loadRuntime = loadRuntime
    this.#clock = clock
    this.#newId = newId
  }

  handle(request: WorkerRequest): Promise<WorkerResponse> {
    const response = this.#queue.then(() => this.#process(request))
    this.#queue = response.then(
      () => undefined,
      () => undefined,
    )
    return response
  }

  #runtime(): Promise<WasmRuntime> {
    this.#runtimePromise ??= this.#loadRuntime().catch((error: unknown) => {
      throw new Error(
        `WASM runtime failed to start: ${errorMessage(error)}. `
        + 'Run `make wasm-build` and reload the application.',
      )
    })
    return this.#runtimePromise
  }

  async #process(request: WorkerRequest): Promise<WorkerResponse> {
    if (!request || typeof request.id !== 'string' || typeof request.operation !== 'string') {
      return failure('', 'bad_request', 'invalid worker request envelope')
    }
    if (!OPERATIONS.has(request.operation)) {
      return failure(request.id, 'bad_request', `unknown worker operation '${request.operation}'`)
    }
    try {
      const runtime = await this.#runtime()
      switch (request.operation) {
        case 'initialize': {
          const snapshot = request.snapshot == null ? undefined : JSON.stringify(request.snapshot)
          return this.#invoke(request.id, runtime.initialize(snapshot))
        }
        case 'execute': {
          let command = request.payload
          if (isRuntimeRequest(request.payload)) {
            const route = dispatchRoute(request.payload, this.#clock(), this.#newId)
            if (route.operation !== 'execute')
              throw new RouteDispatchError(`${request.payload.method} routes must use the query worker operation`)
            command = route.payload
          }
          else if (isRecord(request.payload)) {
            command = { ...request.payload, now: request.payload.now ?? this.#clock() }
          }
          const response = this.#invoke(request.id, runtime.execute(JSON.stringify(command)))
          return response.ok ? this.#withSnapshot(runtime, response) : response
        }
        case 'query': {
          let query = request.payload
          if (isRuntimeRequest(request.payload)) {
            const route = dispatchRoute(request.payload, this.#clock(), this.#newId)
            if (route.operation !== 'query')
              throw new RouteDispatchError(`${request.payload.method} routes must use the execute worker operation`)
            query = route.payload
          }
          return this.#invoke(request.id, runtime.query(JSON.stringify(query)))
        }
        case 'snapshot':
          return this.#invoke(request.id, runtime.snapshot())
        case 'reset': {
          const response = this.#invoke(request.id, runtime.reset())
          return response.ok ? this.#withSnapshot(runtime, response) : response
        }
        case 'seed': {
          const response = this.#invoke(request.id, runtime.seed())
          return response.ok ? this.#withSnapshot(runtime, response) : response
        }
      }
    }
    catch (error) {
      if (error instanceof RouteDispatchError)
        return failure(request.id, 'bad_request', error.message)
      return failure(request.id, 'internal', errorMessage(error))
    }
  }

  #invoke(id: string, json: string): WorkerResponse {
    const response = parseRuntimeResponse(json)
    return response.ok ? success(id, response.result) : { id, ...response }
  }

  #withSnapshot(runtime: WasmRuntime, response: WorkerSuccess): WorkerResponse {
    const snapshotResponse = parseRuntimeResponse(runtime.snapshot())
    return snapshotResponse.ok
      ? success(response.id, response.result, snapshotResponse.result)
      : { id: response.id, ...snapshotResponse }
  }
}
