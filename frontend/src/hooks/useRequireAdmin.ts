/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/**
 * Redirects away from admin-only pages: to /login if not signed in at all,
 * to / if signed in but not an admin - these are different situations and
 * shouldn't both land on the login form. Mirrors this app's existing
 * no-wrapper, inline-useEffect gating convention (see Account.tsx), shared
 * here since every admin page needs the same two-branch check.
 */
export default function useRequireAdmin() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (loading) return
    if (!user) {
      navigate('/login', { replace: true })
      return
    }
    if (!user.is_admin) {
      navigate('/', { replace: true })
    }
  }, [loading, user, navigate])

  return { user, loading }
}
