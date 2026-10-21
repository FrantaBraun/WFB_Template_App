/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, formatDay, formatTime, isoDay, weekdayName, type Info } from './api'
import { mutedClass } from './ui'

/** Whether the pub is open on a date, and its hours - a one-off change of that date wins over the weekday's regular hours. */
export function statusOn(info: Info, date: Date): { open: boolean; opens: string | null; closes: string | null; reason: string | null } {
  const exception = info.exceptions.find((entry) => entry.day === isoDay(date))
  if (exception) {
    const open = !exception.is_closed && !!exception.opens && !!exception.closes
    return { open, opens: open ? exception.opens : null, closes: open ? exception.closes : null, reason: exception.reason }
  }
  const regular = info.weekly.find((entry) => entry.weekday === (date.getDay() + 6) % 7)
  const open = !!regular && !regular.is_closed && !!regular.opens && !!regular.closes
  return { open, opens: open ? regular!.opens : null, closes: open ? regular!.closes : null, reason: null }
}

/** The week's opening hours as a list, with the coming one-off changes (closed days, other hours) below it. */
export function HoursList({ info }: { info: Info }) {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {info.weekly.map((entry) => (
          <div key={entry.weekday} className="contents">
            <dt className="capitalize">{weekdayName(entry.weekday, language)}</dt>
            <dd className={entry.is_closed ? mutedClass : ''}>
              {entry.is_closed || !entry.opens || !entry.closes ? t('hours.closed') : `${formatTime(entry.opens)}–${formatTime(entry.closes)}`}
            </dd>
          </div>
        ))}
      </dl>
      {info.exceptions.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">{t('hours.exceptionsTitle')}</h3>
          <ul className="space-y-1 text-sm">
            {info.exceptions.map((entry) => (
              <li key={entry.day}>
                <span className="font-medium">{formatDay(entry.day, language, 'short')}</span>:{' '}
                {entry.is_closed || !entry.opens || !entry.closes ? t('hours.closed') : `${formatTime(entry.opens)}–${formatTime(entry.closes)}`}
                {entry.reason && <span className={mutedClass}> – {entry.reason}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * The pub's opening hours for an application's own page (exported from the
 * module, e.g. the home page): a line about today - open until when, or closed and
 * why - and the week below it. It fetches what it shows and renders nothing
 * while loading or when the request fails (a side panel should not show an error).
 */
export default function OpeningHours() {
  const { t } = useTranslation('table_reservations')
  const [info, setInfo] = useState<Info | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<Info>(`${API_BASE}/info`)
      .then((found) => !cancelled && setInfo(found))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (!info) return null
  const today = statusOn(info, new Date())
  return (
    <div className="space-y-4">
      <p className="text-base font-medium" role="status">
        {today.open && today.opens && today.closes ? (
          <span className="text-hop dark:text-hop-dark">{t('hours.openToday', { opens: formatTime(today.opens), closes: formatTime(today.closes) })}</span>
        ) : (
          <span className="text-brick dark:text-copper">
            {t('hours.closedToday')}
            {today.reason && <span className={`font-normal ${mutedClass}`}> – {today.reason}</span>}
          </span>
        )}
      </p>
      <HoursList info={info} />
    </div>
  )
}
