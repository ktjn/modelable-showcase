// Minimal HTTP client for the showcase Axum API (IMPLEMENTATION_PLAN.md Task
// 10.1). Defaults to '' (same-origin, relative paths) - vite.config.ts's dev
// server proxies /api to apps/api's default SHOWCASE_API_ADDR, avoiding CORS
// (apps/api has no CORS middleware; a real deployment would put both behind
// one reverse proxy - Phase 11). Override with VITE_API_BASE_URL if apps/api
// is reachable directly some other way.
//
// The generated OpenAPI/TypeScript targets and the Rust API's JSON wire
// format both use camelCase (Modelable 1.9.4, see UPSTREAM_FINDINGS.md #39),
// so no key-casing conversion is needed at this boundary.

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })
  const text = await response.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new ApiError(response.status, body)
  }
  return body as T
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}
