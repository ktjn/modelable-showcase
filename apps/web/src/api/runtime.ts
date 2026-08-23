import { WasmShowcaseRuntime } from '../wasm/showcase-runtime'
import { ApiError } from './runtime-contract'
import type { RuntimeInfo, RuntimeRequest, ShowcaseRuntime } from './runtime-contract'

export { ApiError } from './runtime-contract'
export type { RuntimeInfo, RuntimeKind, RuntimeMethod, RuntimeRequest, ShowcaseRuntime } from './runtime-contract'

export class HttpRuntime implements ShowcaseRuntime {
  readonly kind = 'http' as const
  readonly #baseUrl: string
  readonly #fetch: typeof fetch | undefined

  constructor(
    baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '',
    fetchImplementation?: typeof fetch,
  ) {
    this.#baseUrl = baseUrl
    this.#fetch = fetchImplementation
  }

  async request<T>({ method, path, body }: RuntimeRequest): Promise<T> {
    const response = await (this.#fetch ?? globalThis.fetch)(`${this.#baseUrl}${path}`, {
      method,
      headers: { 'content-type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    const text = await response.text()
    const responseBody: unknown = text ? JSON.parse(text) : null
    if (!response.ok)
      throw new ApiError(response.status, responseBody)
    return responseBody as T
  }

  info(): Promise<RuntimeInfo> {
    return this.request<RuntimeInfo>({ method: 'GET', path: '/api/runtime' })
  }
}

export function createConfiguredRuntime(
  configured = import.meta.env.VITE_SHOWCASE_RUNTIME as string | undefined,
): ShowcaseRuntime {
  switch (configured ?? 'http') {
    case 'http':
      return new HttpRuntime()
    case 'wasm':
      return new WasmShowcaseRuntime()
    default:
      throw new Error(`Unsupported VITE_SHOWCASE_RUNTIME '${configured}'; expected 'http' or 'wasm'`)
  }
}
