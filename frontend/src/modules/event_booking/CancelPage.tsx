/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { API_BASE, fetchJson, formatDateTime, formatSlot, statusOf, type BookingPublic } from './api'
import { cardClass, dangerButtonClass, errorClass, mutedClass, okClass, PageMessage, useNoindexMeta } from './ui'

/**
 * /bookings/cancel/:token - the page the link in the confirmation e-mail
 * opens. It shows the booking and a button; the cancellation itself is a POST
 * pressed here, never something opening the link does (a mail client or a bot
 * may open links on its own). Pressing it again changes nothing. Public: the
 * token is the secret. It shows nothing an administrator wrote.
 */
export default function CancelPage() {
  const { t, i18n } = useTranslation('event_booking')
  const { token } = useParams<{ token: string }>()
  useNoindexMeta(t('cancel.title'))
  const [booking, setBooking] = useState<BookingPublic | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const [justCancelled, setJustCancelled] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchJson<BookingPublic>(`${API_BASE}/bookings/${encodeURIComponent(token ?? '')}`)
      .then((found) => {
        if (cancelled) return
        setBooking(found)
        setState('ready')
      })
      .catch((err) => !cancelled && setState(statusOf(err) === 404 ? 'missing' : 'error'))
    return () => {
      cancelled = true
    }
  }, [token])

  async function cancel() {
    if (!window.confirm(t('cancel.confirm'))) return
    setBusy(true)
    setFailed(false)
    try {
      const updated = await fetchJson<BookingPublic>(`${API_BASE}/bookings/${encodeURIComponent(token ?? '')}/cancel`, { method: 'POST' })
      setBooking(updated)
      setJustCancelled(true)
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  if (state === 'loading') return <PageMessage>{t('common.loading')}</PageMessage>
  if (state === 'missing') return <PageMessage>{t('cancel.notFound')}</PageMessage>
  if (state === 'error' || !booking) return <PageMessage>{t('cancel.loadError')}</PageMessage>

  return (
    <div className="mx-auto max-w-xl px-4 py-10 text-slate-900 sm:px-6 sm:py-14 dark:text-slate-100">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight sm:text-3xl">{t('cancel.title')}</h1>
      <div className={`${cardClass} space-y-3`}>
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className={mutedClass}>{t('cancel.event')}</dt>
          <dd className="font-medium">{booking.event_title}</dd>
          <dt className={mutedClass}>{t('cancel.registration')}</dt>
          <dd>{booking.registration_name}</dd>
          <dt className={mutedClass}>{t('cancel.when')}</dt>
          <dd>{formatSlot(booking.slot_date, booking.slot_time, i18n.language, t('picker.allDay'))}</dd>
          <dt className={mutedClass}>{t('cancel.name')}</dt>
          <dd>{booking.name}</dd>
        </dl>

        {booking.status === 'confirmed' ? (
          <div className="space-y-2 pt-2">
            <p className="text-sm">{t('cancel.question')}</p>
            <button type="button" onClick={cancel} disabled={busy} className={dangerButtonClass}>
              {busy ? t('cancel.cancelling') : t('cancel.button')}
            </button>
            {failed && <p role="alert" className={errorClass}>{t('cancel.failed')}</p>}
          </div>
        ) : (
          <p role="status" className={`pt-2 ${okClass}`}>
            {justCancelled ? t('cancel.done') : t('cancel.alreadyCancelled')}
            {booking.cancelled_at && ` (${formatDateTime(booking.cancelled_at, i18n.language)})`}
          </p>
        )}
      </div>
      <p className="mt-6 text-sm">
        <Link to="/" className="underline">{t('cancel.home')}</Link>
      </p>
    </div>
  )
}
