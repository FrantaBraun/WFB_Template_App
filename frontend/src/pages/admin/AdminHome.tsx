/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'
// From moduleStore, not registry: see the note at the top of modules/moduleStore.ts.
import { useEnabledModules } from '../../modules/moduleStore'

/**
 * The administration areas. A tile that belongs to a module is shown only
 * while that module is enabled, so switching one off leaves no dead link.
 */
const TILES: { to: string; labelKey: string; module?: string }[] = [
  { to: '/admin/pages', labelKey: 'admin.pagesLink' },
  { to: '/articles/manage', labelKey: 'admin.articlesLink', module: 'articles' },
  { to: '/articles/manage/types', labelKey: 'admin.articleTypesLink', module: 'articles' },
  { to: '/events/manage', labelKey: 'admin.eventsLink', module: 'event_calendar' },
  { to: '/bookings/manage', labelKey: 'admin.registrationsLink', module: 'event_booking' },
]

export default function AdminHome() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.pageTitle'), description: t('admin.pageDescription'), noindex: true })
  const { user, loading } = useRequireAdmin()
  const enabled = new Set(useEnabledModules().map((module) => module.key))

  if (loading || !user?.is_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('admin.dashboardTitle')}</h1>
      <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2">
        {TILES.filter((tile) => !tile.module || enabled.has(tile.module)).map((tile) => (
          <Link
            key={tile.to}
            to={tile.to}
            className="rounded-2xl border border-slate-200 bg-white p-6 font-medium hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
          >
            {t(tile.labelKey)}
          </Link>
        ))}
      </div>
    </div>
  )
}
