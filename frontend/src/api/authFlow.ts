/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { TFunction } from 'i18next'
import { getAuthUrl } from './client'

/** What a user with a second factor can answer with (`methods` of a 403 mfa_required). */
export type MfaMethod = 'totp' | 'backup_code'

/**
 * A sign-in that is waiting for its second step: the password (or the Google
 * code) was right, the auth service answered 403 `mfa_required`. `mfaToken` is
 * proof of that first step, valid for 5 minutes, and an opaque string - keep it
 * in memory only (component state), never in storage or the URL.
 */
export interface MfaChallenge {
  mfaToken: string
  methods: MfaMethod[]
}

export type SignInErrorKind =
  | 'invalid_code' // 401 on the second step: wrong authenticator / backup code
  | 'expired' // 401 on the second step: the mfa_token is older than 5 minutes
  | 'rate_limited' // 429: too many wrong passwords or codes
  | 'level_insufficient' // 403 auth_level_insufficient: the application demands a stronger sign-in
  | 'other'

/**
 * A failed sign-in step. `kind` says what happened so the page can word it in
 * the visitor's language (see signInErrorMessage); `message` is the auth
 * service's own text, used only for the failures nothing more specific covers
 * (e.g. "Invalid credentials").
 */
export class SignInError extends Error {
  kind: SignInErrorKind
  hint?: string
  requiredLevel?: number

  constructor(kind: SignInErrorKind, message: string, extra: { hint?: string; requiredLevel?: number } = {}) {
    super(message)
    this.name = 'SignInError'
    this.kind = kind
    this.hint = extra.hint
    this.requiredLevel = extra.requiredLevel
  }
}

const KNOWN_METHODS: MfaMethod[] = ['totp', 'backup_code']

/**
 * The second step the 403 asks for, or null when `body` is some other 403.
 * Methods this app has no screen for (a passkey, say) are dropped; if none are
 * left it falls back to the authenticator app, which every second factor starts with.
 */
export function extractMfaChallenge(body: any): MfaChallenge | null {
  const detail = body?.detail
  if (!detail || typeof detail !== 'object' || !detail.mfa_required || typeof detail.mfa_token !== 'string') {
    return null
  }
  const offered: MfaMethod[] = Array.isArray(detail.methods)
    ? detail.methods.filter((m: unknown): m is MfaMethod => KNOWN_METHODS.includes(m as MfaMethod))
    : []
  return { mfaToken: detail.mfa_token, methods: offered.length ? offered : ['totp'] }
}

/**
 * Turns a failed sign-in response (its status and already-parsed JSON body)
 * into a SignInError. `secondStep` says the request was POST
 * /api/auth/login/mfa, where a 401 means a wrong or expired code rather than
 * wrong credentials.
 */
export function buildSignInError(status: number, body: any, secondStep = false): SignInError {
  const detail = body?.detail
  const text = typeof detail === 'string' ? detail : ''

  if (status === 429) return new SignInError('rate_limited', text)
  if (status === 403 && detail && typeof detail === 'object' && detail.auth_level_insufficient) {
    return new SignInError('level_insufficient', text, {
      hint: detail.hint,
      requiredLevel: detail.required_level,
    })
  }
  if (secondStep && status === 401) {
    // Both 401s of that endpoint differ only in their text: "MFA challenge is
    // invalid or has expired" (start over) vs "Invalid verification code" (try again).
    return new SignInError(/expired/i.test(text) ? 'expired' : 'invalid_code', text)
  }
  return new SignInError('other', text)
}

/** The visitor-facing text of a sign-in failure (`fallback` for kind 'other' without a message of its own). */
export function signInErrorMessage(err: unknown, t: TFunction, fallback: string): string {
  if (!(err instanceof SignInError)) return err instanceof Error && err.message ? err.message : fallback
  switch (err.kind) {
    case 'invalid_code':
      return t('login.mfa.invalidCode')
    case 'expired':
      return t('login.mfa.expired')
    case 'rate_limited':
      return t('login.rateLimited')
    case 'level_insufficient':
      // enroll_mfa: the user has no second factor yet and can turn one on at
      // the auth service. Anything else (a passkey is needed) cannot be done
      // from this application's own sign-in page.
      return err.hint === 'enroll_mfa'
        ? t('login.levelEnrollMfa', { url: getAuthUrl() })
        : t('login.levelInsufficient')
    default:
      return err.message || fallback
  }
}
