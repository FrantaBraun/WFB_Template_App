/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

type IconProps = { className?: string }

function LayersIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  )
}

function BellIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

function FolderIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    </svg>
  )
}

function OverlapIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <circle cx="9" cy="12" r="6" />
      <circle cx="15" cy="12" r="6" />
    </svg>
  )
}

function BookIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  )
}

function UsersIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}

const FEATURES: { key: string; icon: React.ReactNode }[] = [
  { key: 'registry', icon: <LayersIcon className="h-5 w-5" /> },
  { key: 'notifications', icon: <BellIcon className="h-5 w-5" /> },
  { key: 'collections', icon: <FolderIcon className="h-5 w-5" /> },
  { key: 'integrations', icon: <OverlapIcon className="h-5 w-5" /> },
  { key: 'knowledgeBase', icon: <BookIcon className="h-5 w-5" /> },
  { key: 'sharing', icon: <UsersIcon className="h-5 w-5" /> },
]

const EXAMPLE_KEYS = ['microservices', 'paymentProviders', 'integrationScoped'] as const

/**
 * One capability card: an icon, a title and a one-line summary are always
 * visible; hovering (group/group-hover, no JS state) reveals a fuller
 * description via a grid-template-rows 0fr->1fr transition, which animates
 * to the description's natural height instead of a guessed max-height - CS
 * and EN copy differ in length and both need to fit without clipping.
 */
function FeatureCard({ icon, titleKey, summaryKey, detailKey }: { icon: React.ReactNode; titleKey: string; summaryKey: string; detailKey: string }) {
  const { t } = useTranslation()

  return (
    <div className="group rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700">
      <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 transition-colors group-hover:bg-violet-100 group-hover:text-violet-700 dark:bg-slate-800 dark:text-slate-300 dark:group-hover:bg-violet-900/40 dark:group-hover:text-violet-300">
        {icon}
      </div>
      <h3 className="font-semibold text-slate-900 dark:text-slate-100">{t(titleKey)}</h3>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t(summaryKey)}</p>
      <div className="grid grid-rows-[0fr] opacity-0 transition-all duration-300 ease-out group-hover:mt-2 group-hover:grid-rows-[1fr] group-hover:opacity-100">
        <p className="overflow-hidden text-sm text-slate-500 dark:text-slate-400">{t(detailKey)}</p>
      </div>
    </div>
  )
}

/**
 * Public landing page - no auth required. A hero intro to the product with
 * auth-aware calls to action, a hover-reveal grid of feature cards, and a
 * few concrete usage examples.
 */
export default function HomePage() {
  const { t } = useTranslation()
  usePageMeta({ title: t('home.pageTitle'), description: t('home.pageDescription') })
  const { user } = useAuth()

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-20 px-6 py-16 text-slate-900 dark:text-slate-100">
      <section className="flex flex-col items-center gap-6 text-center">
        <div className="rounded-2xl bg-slate-100 p-4 shadow-lg">
          <img src="/logo.png" alt="" className="h-12 w-auto object-contain" />
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t('home.hero.title')}</h1>
          <p className="text-xl font-medium text-slate-700 dark:text-slate-300">{t('home.hero.tagline')}</p>
          <p className="mx-auto max-w-2xl text-slate-600 dark:text-slate-400">{t('home.hero.description')}</p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/api-docs"
            className="rounded-lg bg-slate-900 px-6 py-3 text-sm font-medium text-slate-100 transition-colors hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300"
          >
            {t('home.hero.ctaBrowse')}
          </Link>
          <Link
            to={user ? '/teams' : '/register'}
            className="rounded-lg border border-slate-300 px-6 py-3 text-sm font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-900"
          >
            {t(user ? 'home.hero.ctaTeamsLoggedIn' : 'home.hero.ctaTeamsLoggedOut')}
          </Link>
        </div>
      </section>

      <section>
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">{t('home.features.heading')}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t('home.features.subheading')}</p>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ key, icon }) => (
            <FeatureCard
              key={key}
              icon={icon}
              titleKey={`home.features.${key}.title`}
              summaryKey={`home.features.${key}.summary`}
              detailKey={`home.features.${key}.detail`}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight">{t('home.examples.heading')}</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {EXAMPLE_KEYS.map((key, index) => (
            <div key={key} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
              <span className="mb-3 inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-slate-100 dark:bg-slate-100 dark:text-slate-900">
                {index + 1}
              </span>
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">{t(`home.examples.${key}.title`)}</h3>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{t(`home.examples.${key}.text`)}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
