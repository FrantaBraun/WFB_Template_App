/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, MENU_PATH, fetchJson, isoDay, type DailyWeek } from './api'
import { DayCard } from './MenuPage'
import { mutedClass } from './ui'

/**
 * Today's lunch menu with a link to the whole menu - for an application's own
 * home page (exported from the module). Shows a short note when nothing is
 * published for today, and nothing at all while loading or when the request fails
 * (a home page should not show an error for a side panel).
 */
export default function TodayMenu() {
  const { t } = useTranslation('pub_menu')
  const [week, setWeek] = useState<DailyWeek | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<DailyWeek>(`${API_BASE}/daily`)
      .then((found) => !cancelled && setWeek(found))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (!week) return null
  const today = isoDay(new Date())
  const entry = week.days.find((day) => day.day === today) ?? { day: today, items: [] }

  return (
    <div className="space-y-3">
      <DayCard entry={entry} currency={week.currency} isToday />
      <p className={mutedClass}>
        <Link to={MENU_PATH} className="underline">{t('today.whole')}</Link>
      </p>
    </div>
  )
}
