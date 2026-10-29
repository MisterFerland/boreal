let csrf = ''
export function setCsrf(value: string) {
  csrf = value
}
export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.method && options.method !== 'GET') {
    if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    if (csrf) headers.set('X-CSRF-Token', csrf)
    headers.set('Idempotency-Key', crypto.randomUUID())
  }
  const response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin' })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new ApiError(
      typeof detail === 'string' ? detail : detail?.message || `HTTP ${response.status}`,
      detail?.code || 'REQUEST_FAILED',
      response.status,
    )
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>)
}
export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body) })
}
