export type RuntimeErrorCategory =
  | 'bad_request'
  | 'not_found'
  | 'conflict'
  | 'validation'
  | 'internal'

export interface RuntimeError {
  category: RuntimeErrorCategory
  message: string
}

export type WorkerOperation = 'initialize' | 'execute' | 'query' | 'snapshot' | 'reset' | 'seed'

export interface WorkerRequest {
  id: string
  operation: WorkerOperation
  payload?: unknown
  snapshot?: unknown
}

export interface WorkerSuccess {
  id: string
  ok: true
  result: unknown
  snapshot?: unknown
}

export interface WorkerFailure {
  id: string
  ok: false
  error: RuntimeError
}

export type WorkerResponse = WorkerSuccess | WorkerFailure
