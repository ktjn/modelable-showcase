export type RuntimeMethod = 'GET' | 'POST' | 'PATCH'
export type RuntimeKind = 'http' | 'wasm'

export interface RuntimeRequest {
  method: RuntimeMethod
  path: string
  body?: unknown
}

export interface ShowcaseRuntime {
  request<T>(request: RuntimeRequest): Promise<T>
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(
      isPlainObject(body) && typeof body.error === 'string'
        ? body.error
        : `API request failed with status ${status}`,
    )
    this.status = status
    this.body = body
  }
}
