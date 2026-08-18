// Minimal HTTP client for the showcase Axum API (IMPLEMENTATION_PLAN.md Task
// 10.1). Defaults to '' (same-origin, relative paths) - vite.config.ts's dev
// server proxies /api to apps/api's default SHOWCASE_API_ADDR, avoiding CORS
// (apps/api has no CORS middleware; a real deployment would put both behind
// one reverse proxy - Phase 11). Override with VITE_API_BASE_URL if apps/api
// is reachable directly some other way.
//
// UPSTREAM_FINDINGS.md #39: the generated OpenAPI/TypeScript targets use
// Modelable's source camelCase field names, but the generated Rust API's
// actual JSON wire format is snake_case (no serde rename). toSnakeCase/
// toCamelCase below convert at this one boundary so the rest of the app can
// keep using the generated camelCase types throughout.

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

function toSnakeCase(key: string): string {
  return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

function toCamelCase(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_match, letter: string) => letter.toUpperCase())
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function convertKeys(value: unknown, convert: (key: string) => string): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => convertKeys(item, convert))
  }
  if (isPlainObject(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, val]) => [convert(key), convertKeys(val, convert)]))
  }
  return value
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
  return convertKeys(body, toCamelCase) as T
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(convertKeys(body, toSnakeCase)) })
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(convertKeys(body, toSnakeCase)) })
}
