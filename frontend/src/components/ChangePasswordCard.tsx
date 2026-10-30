/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api/client'

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'

/**
 * Change-password card on the Account page. The backend forwards the
 * current and new password to the auth service, which checks the current
 * one. It keeps its own form state, so a failure here never touches the
 * profile card.
 */
export default function ChangePasswordCard() {
  const { t } = useTranslation()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: t('account.passwordCard.mismatch') })
      return
    }
    setSaving(true)
    try {
      const resp = await apiFetch('/api/auth/me/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      if (!resp.ok) throw new Error()
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setMessage({ type: 'success', text: t('account.passwordCard.success') })
    } catch {
      setMessage({ type: 'error', text: t('account.passwordCard.error') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {t('account.passwordCard.title')}
      </h2>

      <div>
        <label htmlFor="current-password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
          {t('account.passwordCard.currentLabel')}
        </label>
        <input
          id="current-password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
          autoComplete="current-password"
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="account-new-password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
          {t('account.passwordCard.newLabel')}
        </label>
        <input
          id="account-new-password"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="account-confirm-password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
          {t('account.passwordCard.confirmLabel')}
        </label>
        <input
          id="account-confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
          className={inputClass}
        />
      </div>

      {message && (
        <p
          className={`text-sm ${
            message.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
          }`}
        >
          {message.text}
        </p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
      >
        {saving ? t('account.passwordCard.submitting') : t('account.passwordCard.submit')}
      </button>
    </form>
  )
}
