/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearTokens, getRefreshToken, setTokens } from '../api/client'
import { apiFetch } from '../api/client'
import { applyUserLanguage } from '../i18n'
import { useTheme } from './ThemeContext'

interface AuthContextType {
  user: any | null
  loading: boolean
  login: (identifier: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: any) => void
  loadUser: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  setUser: () => {},
  loadUser: async () => false,
})

/**
 * Pulls the application_group_id out of a 403 error body when it represents
 * a consent_required response, or null otherwise.
 * err.detail is an object for consent_required ({consent_required, application_group_id}),
 * not a string - `new Error(err.detail)` would silently stringify it to "[object Object]".
 */
function extractConsentGroupId(body: any): string | null {
  const detail = body?.detail
  if (detail && typeof detail === 'object' && detail.consent_required) {
    return detail.application_group_id ?? null
  }
  return null
}

/** Provides auth state (user, loading) and actions (login, logout, loadUser) to the component tree. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { setDarkMode, setProfileDarkMode } = useTheme()

  const redirectToConsent = useCallback(
    (groupId: string) => {
      // /login, /oauth/callback and /consent itself are transient auth-flow
      // pages, never a destination the user was actually trying to reach -
      // if consent gets (re-)detected while already on one of these (e.g.
      // loadUser() called from within login() itself, or called again on a
      // stray effect re-run), capturing it as the redirect target would send
      // the user back to an empty login form, or nest /consent inside its
      // own redirect param. Fall back to home instead.
      const currentPath = window.location.pathname
      const isTransientAuthPage = ['/login', '/oauth/callback', '/consent'].includes(currentPath)
      const redirectTo = isTransientAuthPage ? '/' : currentPath + window.location.search
      navigate(`/consent?group=${groupId}&redirect=${encodeURIComponent(redirectTo)}`, { replace: true })
    },
    [navigate],
  )

  const loadUser = useCallback(async (): Promise<boolean> => {
    const resp = await apiFetch('/api/auth/me').catch(() => null)
    if (resp?.ok) {
      const userData = await resp.json()
      setUser(userData)
      // Switch to the signed-in user's own language preference (with a
      // supported-language/EN/leave-as-is fallback) rather than whatever
      // the browser or a pre-login manual choice left active.
      applyUserLanguage(userData.language_code)
      // Best-effort sync of the stored dark-mode preference (lives in
      // group-attributes' user_data, not on UserOut itself, so it needs its
      // own request). Only overrides the local theme if the profile has an
      // explicit value - a user who never set one keeps whatever was active
      // (localStorage/toggle) rather than being forced to light.
      if (userData.application_group_id) {
        apiFetch(`/api/auth/me/group-attributes/${userData.application_group_id}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            const stored = typeof data?.user_data?.darkMode === 'boolean' ? data.user_data.darkMode : false
            setProfileDarkMode(stored)
            if (typeof data?.user_data?.darkMode === 'boolean') {
              setDarkMode(data.user_data.darkMode)
            }
          })
          .catch(() => {})
      }
      return true
    }
    if (resp?.status === 403) {
      const groupId = extractConsentGroupId(await resp.json().catch(() => ({})))
      if (groupId) {
        // The user IS validly authenticated, just missing consent - keep
        // their tokens so retrying /me after granting succeeds immediately.
        redirectToConsent(groupId)
        return false
      }
    }
    clearTokens()
    setUser(null)
    return false
  }, [redirectToConsent, setDarkMode, setProfileDarkMode])

  useEffect(() => {
    if (localStorage.getItem('access_token')) {
      loadUser().finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
    // Intentionally run once on mount only. loadUser's identity depends on
    // navigate (via redirectToConsent), which react-router doesn't guarantee
    // is referentially stable across navigations - depending on [loadUser]
    // here caused this initial-session check to re-fire on unrelated route
    // changes, redundantly re-querying /me and, if consent was pending,
    // re-triggering the consent redirect using the *current* (already
    // redirected-to) URL as the new target.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function login(identifier: string, password: string) {
    const resp = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      const groupId = extractConsentGroupId(err)
      if (groupId) {
        redirectToConsent(groupId)
        return
      }
      throw new Error(typeof err.detail === 'string' ? err.detail : 'Login failed')
    }
    const data = await resp.json()
    setTokens(data.access_token, data.refresh_token)
    const loaded = await loadUser()
    if (loaded) {
      navigate('/', { replace: true })
    }
  }

  async function logout() {
    const rt = getRefreshToken()
    if (rt) {
      await apiFetch('/api/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: rt }),
      }).catch(() => null)
    }
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser, loadUser }}>
      {children}
    </AuthContext.Provider>
  )
}

/** Reads the current AuthContextType (user, loading, login/logout/loadUser) from the nearest AuthProvider. */
export function useAuth() {
  return useContext(AuthContext)
}
