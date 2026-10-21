/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import BookingsAdmin from './BookingsAdmin'
import { API_BASE, BOOKINGS_PATH, fetchJson, type RegistrationListItem } from './api'
import { cardClass, mutedClass, secondaryButtonClass } from './ui'

/**
 * The administrators' event list shows one of these per row and each asks for
 * the same list of registrations: share one request among the rows that mount
 * together instead of sending one each.
 */
let sharedList: { at: number; promise: Promise<RegistrationListItem[]> } | null = null
const SHARE_MS = 5000

function loadRegistrations(): Promise<RegistrationListItem[]> {
  if (!sharedList || Date.now() - sharedList.at > SHARE_MS) {
    sharedList = { at: Date.now(), promise: fetchJson<RegistrationListItem[]>(`${API_BASE}/manage/registrations`) }
    sharedList.promise.catch(() => {
      sharedList = null
    })
  }
  return sharedList.promise
}

/**
 * A link in each row of the administrators' event list (contributed to the
 * calendar's "event.manage" slot; context `{ event }`): to the event's
 * registration, or to creating one.
 */
export function ManageRowAction({ context }: { context: { event: { id: string } } }) {
  const { t } = useTranslation('event_booking')
  const [registration, setRegistration] = useState<RegistrationListItem | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    loadRegistrations()
      .then((all) => !cancelled && setRegistration(all.find((item) => item.event_id === context.event.id) ?? null))
      .catch(() => !cancelled && setRegistration(null))
    return () => {
      cancelled = true
    }
  }, [context.event.id])

  if (registration === undefined) return null
  return registration ? (
    <Link to={`${BOOKINGS_PATH}/manage/${registration.id}`} className="text-sm underline">
      {t('row.registration', { count: registration.confirmed_count })}
    </Link>
  ) : (
    <Link to={`${BOOKINGS_PATH}/manage/new?event=${context.event.id}`} className="text-sm underline">
      {t('row.add')}
    </Link>
  )
}

/**
 * The "Registration" panel in the editor of a saved event (contributed to the
 * calendar's "event.editor" slot; context `{ event }`): a summary of the
 * event's registration and the table of its bookings - to open one, change it
 * or cancel it - or a way to create the registration.
 */
export function EventRegistrationPanel({ context }: { context: { event: { id: string } } }) {
  const { t } = useTranslation('event_booking')
  const [registration, setRegistration] = useState<RegistrationListItem | null | undefined>(undefined)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setRegistration(undefined)
    fetchJson<RegistrationListItem[]>(`${API_BASE}/manage/registrations?event_id=${context.event.id}`)
      .then((found) => !cancelled && setRegistration(found[0] ?? null))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [context.event.id])

  return (
    <section aria-labelledby="event-registration-heading" className={`mt-10 ${cardClass} text-slate-900 dark:text-slate-100`}>
      <h2 id="event-registration-heading" className="mb-3 text-xl font-semibold tracking-tight">{t('panelAdmin.title')}</h2>
      {failed && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{t('panelAdmin.loadError')}</p>}
      {registration === undefined && !failed && <p className={mutedClass}>{t('common.loading')}</p>}
      {registration === null && (
        <div className="space-y-3">
          <p className={mutedClass}>{t('panelAdmin.none')}</p>
          <Link to={`${BOOKINGS_PATH}/manage/new?event=${context.event.id}`} className={`inline-block ${secondaryButtonClass}`}>
            {t('panelAdmin.create')}
          </Link>
        </div>
      )}
      {registration && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{registration.name}</p>
              <p className={mutedClass}>
                {t(`access.${registration.access}`)} · {registration.is_open ? t('manage.open') : t('manage.closedState')} ·{' '}
                {t('manage.counts', { confirmed: registration.confirmed_count, cancelled: registration.cancelled_count })}
              </p>
            </div>
            <Link to={`${BOOKINGS_PATH}/manage/${registration.id}`} className={secondaryButtonClass}>
              {t('panelAdmin.fullEditor')}
            </Link>
          </div>
          <BookingsAdmin registrationId={registration.id} />
        </div>
      )}
    </section>
  )
}
