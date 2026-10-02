/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, postJson, type BlockedUser } from './api'

/** Accounts this application has blocked for repeated violations, each with the button that lifts the block. */
export default function ModerationAccounts() {
  const { t } = useTranslation('boards')
  const [users, setUsers] = useState<BlockedUser[] | null>(null)
  const [error, setError] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<BlockedUser[]>(`${API_BASE}/manage/users/blocked`)
      .then((found) => !cancelled && setUsers(found))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [])

  async function unblock(id: string) {
    if (!window.confirm(t('admin.accounts.confirmUnblock'))) return
    setBusyId(id)
    setError(false)
    try {
      await postJson(`${API_BASE}/manage/users/${id}/unblock`)
      setUsers((current) => (current ?? []).filter((user) => user.id !== id))
    } catch {
      setError(true)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="text-sm">
      <p className="mb-4 text-slate-600 dark:text-slate-400">{t('admin.accounts.explain')}</p>
      {error && <p className="mb-4 text-red-600 dark:text-red-400">{t('admin.error')}</p>}
      {users === null ? (
        !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : users.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {t('admin.accounts.empty')}
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {users.map((user) => (
            <li key={user.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <code>{user.id}</code>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {user.blocked_at && new Date(user.blocked_at).toLocaleString()}
                  {user.blocked_reason &&
                    ` · ${t(`admin.reason.${user.blocked_reason}`, { defaultValue: user.blocked_reason })}`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => unblock(user.id)}
                disabled={busyId === user.id}
                className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                {t('admin.accounts.unblock')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
