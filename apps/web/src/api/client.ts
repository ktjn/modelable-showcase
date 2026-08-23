import type { RuntimeMethod, ShowcaseRuntime } from './runtime'
import { createConfiguredRuntime } from './runtime'

export { ApiError } from './runtime'

export interface ShowcaseClient {
  get<T>(path: string): Promise<T>
  post<T>(path: string, body: unknown): Promise<T>
  patch<T>(path: string, body: unknown): Promise<T>
}

export function createShowcaseClient(runtime: ShowcaseRuntime): ShowcaseClient {
  const request = <T>(method: RuntimeMethod, path: string, body?: unknown) => (
    runtime.request<T>({ method, path, ...(body === undefined ? {} : { body }) })
  )
  return {
    get: <T>(path: string) => request<T>('GET', path),
    post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
    patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  }
}

const client = createShowcaseClient(createConfiguredRuntime())

export const get = client.get
export const post = client.post
export const patch = client.patch
