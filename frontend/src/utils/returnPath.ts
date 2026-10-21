/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Where to send a visitor after they sign in. A page that needs a signed-in
// user (a registration for signed-in visitors only, say) calls
// rememberReturnPath(...) and then sends them to /login; the sign-in flow
// (AuthContext.login, the Google callback, the consent redirect) calls
// consumeReturnPath() and goes there instead of to the home page.
//
// Kept in sessionStorage (this tab only) and for a limited time, so an
// abandoned sign-in cannot send somebody somewhere unexpected days later.
// Only a path inside this site is ever accepted - the value is read back from
// storage, so it is treated as untrusted and never allowed to become an
// open redirect.

const KEY = 'auth_return_to'
const MAX_AGE_MS = 30 * 60 * 1000

/** Pages of the sign-in flow itself: never a destination worth returning to. */
const AUTH_PAGES = ['/login', '/register', '/oauth/callback', '/consent', '/consent-rejected']

/** A path inside this site (starts with one "/", no "//", no backslash) that is not an auth page. */
export function isSafeReturnPath(path: unknown): path is string {
  if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return false
  const pathname = path.split(/[?#]/)[0]
  return !AUTH_PAGES.includes(pathname)
}

export function rememberReturnPath(path: string, now: number = Date.now()): void {
  if (!isSafeReturnPath(path)) return
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ path, at: now }))
  } catch {
    // storage unavailable: the visitor simply lands on the home page after signing in
  }
}

/** The remembered path, once - or null when there is none, it has expired or it is not a safe path. */
export function consumeReturnPath(now: number = Date.now()): string | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    if (!raw) return null
    const { path, at } = JSON.parse(raw)
    if (typeof at !== 'number' || now - at > MAX_AGE_MS || now < at) return null
    return isSafeReturnPath(path) ? path : null
  } catch {
    return null
  }
}
