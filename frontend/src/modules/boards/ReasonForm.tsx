/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { MODERATION_REASON_MAX, charCount } from './api'
import { Counter } from './PostForm'

const field =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

/**
 * The small form an administrator fills in to block something: a reason the
 * person concerned is sent, with a counter against the backend's limit. The
 * parent does the blocking in `onSubmit` (and closes the form when it
 * succeeds); while that runs the button is disabled.
 */
export default function ReasonForm({
  id,
  label,
  hint,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  id: string
  label: string
  hint: string
  submitLabel: string
  onSubmit: (reason: string) => Promise<void>
  onCancel: () => void
}) {
  const { t } = useTranslation('boards')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const length = charCount(reason)
  const valid = length > 0 && length <= MODERATION_REASON_MAX

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !valid) return
    setBusy(true)
    try {
      await onSubmit(reason)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-2 rounded-lg border border-slate-300 p-3 text-sm dark:border-slate-700">
      <label htmlFor={id} className="block font-medium">
        {label}
      </label>
      <textarea id={id} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} className={`${field} w-full`} />
      <p className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-slate-500 dark:text-slate-400">{hint}</span>
        <Counter count={length} max={MODERATION_REASON_MAX} />
      </p>
      <div className="flex gap-3">
        <button type="submit" disabled={busy || !valid} className="rounded-lg bg-red-700 px-4 py-1.5 font-medium text-white disabled:opacity-50">
          {busy ? t('common.loading') : submitLabel}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-1.5 dark:border-slate-700">
          {t('admin.cancel')}
        </button>
      </div>
    </form>
  )
}
