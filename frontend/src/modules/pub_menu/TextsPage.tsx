/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, sendJson, type Settings } from './api'
import { ManageShell, Section, errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass } from './ui'

/** /menu/manage/texts - the notes shown under the lunch menu and under the standing menu. */
export default function TextsPage() {
  const { t } = useTranslation('pub_menu')
  return (
    <ManageShell title={t('manage.textsTitle')}>
      <Texts />
    </ManageShell>
  )
}

function Texts() {
  const { t } = useTranslation('pub_menu')
  const [values, setValues] = useState<Settings | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<Settings>(`${API_BASE}/manage/settings`)
      .then((found) => !cancelled && setValues(found))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!values) return
    setBusy(true)
    setMessage(null)
    try {
      setValues(await sendJson<Settings>(`${API_BASE}/manage/settings`, 'PUT', values))
      setMessage({ kind: 'ok', text: t('common.saved') })
    } catch {
      setMessage({ kind: 'error', text: t('errors.generic') })
    } finally {
      setBusy(false)
    }
  }

  if (failed) return <p role="alert" className={errorClass}>{t('manage.loadError')}</p>
  if (!values) return <p className={mutedClass}>{t('common.loading')}</p>

  return (
    <Section title={t('texts.title')}>
      <form onSubmit={save} className="space-y-4">
        <div>
          <label htmlFor="daily-note" className={labelClass}>{t('texts.dailyNote')}</label>
          <textarea id="daily-note" rows={3} maxLength={1000} value={values.daily_note} onChange={(e) => setValues({ ...values, daily_note: e.target.value })} className={inputClass} />
          <p className={`mt-1 ${mutedClass}`}>{t('texts.dailyHint')}</p>
        </div>
        <div>
          <label htmlFor="offer-note" className={labelClass}>{t('texts.offerNote')}</label>
          <textarea id="offer-note" rows={3} maxLength={1000} value={values.offer_note} onChange={(e) => setValues({ ...values, offer_note: e.target.value })} className={inputClass} />
          <p className={`mt-1 ${mutedClass}`}>{t('texts.offerHint')}</p>
        </div>
        {message && <p role={message.kind === 'error' ? 'alert' : 'status'} className={message.kind === 'error' ? errorClass : okClass}>{message.text}</p>}
        <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? t('common.saving') : t('common.save')}</button>
      </form>
    </Section>
  )
}
