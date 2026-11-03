/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

function Icon({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {children}
    </svg>
  )
}

const ICON = 'h-5 w-5'

/** The six icons of the original cards and six more for what was added since: formats, silent changes, breaking changes, search, pinned versions and webhooks. */
const FEATURES: { key: string; icon: ReactNode }[] = [
  {
    key: 'registry',
    icon: (
      <Icon className={ICON}>
        <polygon points="12 2 2 7 12 12 22 7 12 2" />
        <polyline points="2 17 12 22 22 17" />
        <polyline points="2 12 12 17 22 12" />
      </Icon>
    ),
  },
  {
    key: 'formats',
    icon: (
      <Icon className={ICON}>
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </Icon>
    ),
  },
  {
    key: 'notifications',
    icon: (
      <Icon className={ICON}>
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </Icon>
    ),
  },
  {
    key: 'contentChanges',
    icon: (
      <Icon className={ICON}>
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" />
        <circle cx="12" cy="12" r="3" />
      </Icon>
    ),
  },
  {
    key: 'breakingChanges',
    icon: (
      <Icon className={ICON}>
        <path d="m10.29 3.86-8.47 14.14A2 2 0 0 0 3.53 21h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </Icon>
    ),
  },
  {
    key: 'endpointSearch',
    icon: (
      <Icon className={ICON}>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </Icon>
    ),
  },
  {
    key: 'collections',
    icon: (
      <Icon className={ICON}>
        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
      </Icon>
    ),
  },
  {
    key: 'integrations',
    icon: (
      <Icon className={ICON}>
        <circle cx="9" cy="12" r="6" />
        <circle cx="15" cy="12" r="6" />
      </Icon>
    ),
  },
  {
    key: 'pins',
    icon: (
      <Icon className={ICON}>
        <path d="M12 17v5" />
        <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1Z" />
      </Icon>
    ),
  },
  {
    key: 'knowledgeBase',
    icon: (
      <Icon className={ICON}>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      </Icon>
    ),
  },
  {
    key: 'sharing',
    icon: (
      <Icon className={ICON}>
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </Icon>
    ),
  },
  {
    key: 'webhooks',
    icon: (
      <Icon className={ICON}>
        <path d="M22 2 11 13" />
        <path d="M22 2l-7 20-4-9-9-4 20-7Z" />
      </Icon>
    ),
  },
]

const FORMAT_KEYS = ['openapi', 'asyncapi', 'postman', 'graphql'] as const
const STEP_KEYS = ['register', 'watch', 'compare'] as const
const EXAMPLE_KEYS = ['microservices', 'paymentProviders', 'integrationScoped', 'breakingBeforeDeploy', 'pinnedVersion', 'findEndpoint'] as const

/**
 * One capability card: an icon, a title and a one-line summary are always
 * visible; hovering (group/group-hover, no JS state) reveals a fuller
 * description via a grid-template-rows 0fr->1fr transition, which animates
 * to the description's natural height instead of a guessed max-height - CS
 * and EN copy differ in length and both need to fit without clipping.
 */
function FeatureCard({ icon, titleKey, summaryKey, detailKey }: { icon: ReactNode; titleKey: string; summaryKey: string; detailKey: string }) {
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
 * Public landing page - no auth required. A hero intro to the product (short
 * name, full name, auth-aware calls to action and a link to the About page),
 * the formats it keeps, how it works in three steps, a hover-reveal grid of
 * feature cards, a few concrete usage examples and a closing note on who can
 * see what, with links to the Terms and Privacy pages.
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
          <div>
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t('home.hero.title')}</h1>
            <p className="mt-2 text-base font-medium tracking-wide text-violet-600 dark:text-violet-400">{t('home.hero.fullName')}</p>
          </div>
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
          <Link to="/about" className="px-3 py-3 text-sm font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300">
            {t('home.hero.ctaAbout')} →
          </Link>
        </div>
      </section>

      <section className="text-center">
        <h2 className="text-2xl font-semibold tracking-tight">{t('home.formats.heading')}</h2>
        <ul className="mt-5 flex flex-wrap justify-center gap-2">
          {FORMAT_KEYS.map((key) => (
            <li key={key} className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
              {t(`specTypes.${key}`)}
            </li>
          ))}
        </ul>
        <p className="mx-auto mt-4 max-w-2xl text-sm text-slate-500 dark:text-slate-400">{t('home.formats.text')}</p>
      </section>

      <section>
        <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight">{t('home.howItWorks.heading')}</h2>
        <ol className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {STEP_KEYS.map((key, index) => (
            <li key={key} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
              <span className="mb-3 inline-flex h-7 w-7 items-center justify-center rounded-full bg-violet-600 text-xs font-semibold text-white">{index + 1}</span>
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">{t(`home.howItWorks.${key}.title`)}</h3>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{t(`home.howItWorks.${key}.text`)}</p>
            </li>
          ))}
        </ol>
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
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
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

      <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xl font-semibold tracking-tight">{t('home.trust.heading')}</h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">{t('home.trust.text')}</p>
        <nav className="mt-4 flex flex-wrap justify-center gap-x-5 gap-y-1 text-sm">
          {(['about', 'privacy', 'terms'] as const).map((page) => (
            <Link key={page} to={`/${page}`} className="font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300">
              {t(`nav.${page}`, { ns: 'legal' })}
            </Link>
          ))}
        </nav>
      </section>
    </div>
  )
}
