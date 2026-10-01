/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const AUTH_URL = (import.meta.env.VITE_AUTH_URL || 'https://auth.withfbraun.com').replace(/\/$/, '')

let _access  = localStorage.getItem('access_token')  || null
let _refresh = localStorage.getItem('refresh_token') || null

export function setTokens(access: string, refresh: string) {
  _access  = access
  _refresh = refresh
  localStorage.setItem('access_token',  access)
  localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  _access  = null
  _refresh = null
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

/** Returns the in-memory access token (mirrors localStorage, set at module load and via setTokens/clearTokens). */
export function getAccessToken()  { return _access }
/** Returns the in-memory refresh token (mirrors localStorage, set at module load and via setTokens/clearTokens). */
export function getRefreshToken() { return _refresh }
/** Returns this app's own backend base URL (VITE_API_URL), used for every proxied `/api/*` call. */
export function getApiUrl()       { return BASE_URL }
/** Returns the shared auth service's public URL (VITE_AUTH_URL) - the one place the frontend talks to it directly (e.g. the Google OAuth redirect), rather than through this backend. */
export function getAuthUrl()      { return AUTH_URL }

/**
 * Exchanges the stored refresh token for a new access/refresh pair via this
 * app's own `/api/auth/refresh` proxy. On failure, clears tokens and throws
 * so the caller (apiFetch) knows the session is truly gone rather than
 * retrying indefinitely.
 */
async function doRefresh() {
  if (!_refresh) throw new Error('no_refresh')
  const resp = await fetch(`${BASE_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: _refresh }),
  })
  if (!resp.ok) { clearTokens(); throw new Error('session_expired') }
  const data = await resp.json()
  setTokens(data.access_token, data.refresh_token)
  return data.access_token
}

/**
 * Fetch wrapper for all backend calls: prefixes `path` with BASE_URL,
 * attaches the bearer token when present, and on a 401 transparently
 * refreshes the token and retries the request exactly once. If the refresh
 * itself fails, tokens are cleared and the browser is hard-redirected to
 * `/login` (not a router navigate - this runs outside React and needs to
 * work even if the component tree using it has already unmounted).
 */
export async function apiFetch(path: string, options: { method?: string; headers?: {Authorization?: string}, [key: string]: any } = { headers: {}, method: 'GET' }) {
  const url = `${BASE_URL}${path}`
  // A FormData body (file uploads) must let the browser set its own
  // multipart Content-Type with the correct boundary - forcing
  // application/json here would corrupt the request.
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers }
  if (_access) headers.Authorization = `Bearer ${_access}`

  let resp = await fetch(url, { ...options, headers })

  if (resp.status === 401 && _refresh) {
    try {
      const fresh = await doRefresh()
      headers.Authorization = `Bearer ${fresh}`
      resp = await fetch(url, { ...options, headers })
    } catch {
      clearTokens()
      window.location.href = '/login'
      throw new Error('Session expired')
    }
  }

  return resp
}

/**
 * Like apiFetch, but for multipart/form-data uploads (e.g. api-docs' file
 * upload endpoints): same bearer-attach + 401-refresh-retry-once behavior,
 * but deliberately never sets a Content-Type header, unlike apiFetch's
 * unconditional 'application/json' - the browser must generate its own
 * multipart boundary from the FormData body, which an explicit header would
 * break.
 */
export async function apiUpload(path: string, formData: FormData, options: { method?: string; headers?: {Authorization?: string}, [key: string]: any } = { headers: {}, method: 'POST' }) {
  const url = `${BASE_URL}${path}`
  const method = options.method ?? 'POST'
  const headers = { ...options.headers }
  if (_access) headers.Authorization = `Bearer ${_access}`

  let resp = await fetch(url, { ...options, method, body: formData, headers })

  if (resp.status === 401 && _refresh) {
    try {
      const fresh = await doRefresh()
      headers.Authorization = `Bearer ${fresh}`
      resp = await fetch(url, { ...options, method, body: formData, headers })
    } catch {
      clearTokens()
      window.location.href = '/login'
      throw new Error('Session expired')
    }
  }

  return resp
}

/**
 * Decodes a JWT's payload for client-side display purposes only (e.g.
 * reading claims to show in the UI). Does NOT verify the signature - this
 * is purely a base64url decode, so the result must never be trusted for
 * authorization decisions. The backend is the only party that verifies
 * tokens (see backend `app/security/jwt.py`).
 */
export function decodeJwt(token: string) {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
  } catch { return null }
}
