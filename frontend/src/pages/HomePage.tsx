/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import JsonLd from '../components/JsonLd'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'
import { RepositoryList } from '../modules/repository'

const isRegistrationAllowed = (import.meta.env.VITE_REGISTRATION_ALLOWED || 'true') === 'true'
const FEATURES = ['types', 'browse', 'statistics', 'private'] as const
const STEPS = ['repository', 'tables', 'records'] as const
const EXAMPLES = ['collections', 'overviews', 'links'] as const

const cardClass = 'rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900'
const sectionTitleClass = 'text-2xl font-semibold tracking-tight'
const mutedClass = 'text-sm text-slate-600 dark:text-slate-300'

/**
 * The home page of HomeRepository. A visitor who is not signed in reads what
 * the application is for (it is the one page of the application a search
 * engine can index, so its words are the ones people search for); a signed-in
 * user sees their repositories (the repository module's RepositoryList,
 * imported from the module itself - never from its registry, see
 * src/modules/moduleStore.ts).
 */
export default function HomePage() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  usePageMeta({ title: t('home.metaTitle') })

  if (loading) return null

  if (user) {
    return (
      <div className="mx-auto max-w-4xl px-3 py-10 sm:px-6">
        <RepositoryList />
      </div>
    )
  }

  const brand = t('nav.brand')
  const siteUrl = `${window.location.origin}/`

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-14 px-3 py-14 text-slate-900 dark:text-slate-100 sm:px-6">
      <JsonLd id="website" data={{ '@context': 'https://schema.org', '@type': 'WebSite', name: brand, url: siteUrl, inLanguage: ['cs', 'en'] }} />
      <JsonLd
        id="webapplication"
        data={{
          '@context': 'https://schema.org',
          '@type': 'WebApplication',
          name: brand,
          url: siteUrl,
          description: t('meta.description'),
          applicationCategory: 'UtilitiesApplication',
          operatingSystem: 'Any',
          browserRequirements: 'Requires JavaScript',
          inLanguage: ['cs', 'en'],
          featureList: FEATURES.map((feature) => t(`home.features.${feature}.title`)),
        }}
      />

      <section className="space-y-4 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{brand}</p>
        <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">{t('home.title')}</h1>
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
      </section>

      <ul className="grid w-full gap-4 text-left sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <li key={feature} className={cardClass}>
            <h2 className="mb-1 text-lg font-semibold">{t(`home.features.${feature}.title`)}</h2>
            <p className={mutedClass}>{t(`home.features.${feature}.text`)}</p>
          </li>
        ))}
      </ul>

      <section className="space-y-5">
        <h2 className={sectionTitleClass}>{t('home.how.title')}</h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step} className={cardClass}>
              <span
                aria-hidden="true"
                className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-slate-100 dark:bg-slate-100 dark:text-slate-900"
              >
                {index + 1}
              </span>
              <h3 className="mb-1 text-lg font-semibold">{t(`home.how.steps.${step}.title`)}</h3>
              <p className={mutedClass}>{t(`home.how.steps.${step}.text`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-5">
        <h2 className={sectionTitleClass}>{t('home.examples.title')}</h2>
        <ul className="grid gap-4 sm:grid-cols-3">
          {EXAMPLES.map((example) => (
            <li key={example} className={cardClass}>
              <h3 className="mb-1 text-lg font-semibold">{t(`home.examples.items.${example}.title`)}</h3>
              <p className={mutedClass}>{t(`home.examples.items.${example}.text`)}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
