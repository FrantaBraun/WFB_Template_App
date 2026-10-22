/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'
import { RepositoryList } from '../modules/repository'

const isRegistrationAllowed = (import.meta.env.VITE_REGISTRATION_ALLOWED || 'true') === 'true'
const FEATURES = ['types', 'browse', 'statistics', 'private'] as const

/**
 * The home page of HomeRepository. A visitor who is not signed in reads what
 * the application is for; a signed-in user sees their repositories (the
 * repository module's RepositoryList, imported from the module itself - never
 * from its registry, see src/modules/moduleStore.ts).
 */
export default function HomePage() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  usePageMeta()

  if (loading) return null

  if (user) {
    return (
      <div className="mx-auto max-w-4xl px-3 py-10 sm:px-6">
        <RepositoryList />
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col items-center gap-10 px-3 py-14 text-center text-slate-900 dark:text-slate-100 sm:px-6">
      <div className="space-y-4">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t('home.title')}</h1>
        <p className="mx-auto max-w-xl text-lg text-slate-600 dark:text-slate-300">{t('home.description')}</p>
        <div className="flex flex-wrap justify-center gap-3 pt-2">
          <Link to="/login" className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-slate-100 hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300">
            {t('home.signIn')}
          </Link>
          {isRegistrationAllowed && (
            <Link to="/register" className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
              {t('home.register')}
            </Link>
          )}
        </div>
      </div>

      <ul className="grid w-full gap-4 text-left sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <li key={feature} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-1 text-lg font-semibold">{t(`home.features.${feature}.title`)}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">{t(`home.features.${feature}.text`)}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
