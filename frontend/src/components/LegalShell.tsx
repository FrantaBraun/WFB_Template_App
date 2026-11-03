/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { isProviderConfigured, legalVars, useLegalConfig, type LegalConfig } from '../config/legal'
import usePageMeta from '../hooks/usePageMeta'

export const LEGAL_PATHS = { about: '/about', terms: '/terms', privacy: '/privacy' } as const

/** One block of a legal text, as the `legal` locales write it. */
export interface LegalSection {
  title: string
  paragraphs?: string[]
  items?: string[]
}

/**
 * Chrome and data loading shared by the About, Terms and Privacy pages: the
 * page title and description, the provider details from public/legal.json
 * (`children` gets them, with the interpolation values every text uses), a
 * warning while the provider has not filled in the minimum, the "effective
 * from" date and the links between the three pages.
 */
export default function LegalShell({
  page,
  children,
}: {
  page: 'about' | 'terms' | 'privacy'
  children: (config: LegalConfig, vars: Record<string, string>) => ReactNode
}) {
  const { t, i18n } = useTranslation('legal')
  const config = useLegalConfig()
  // The application's name goes into the heading and the meta tags too, so it is known before the provider's details are loaded.
  const brand = { app: t('nav.brand', { ns: 'translation' }), fullName: t('nav.fullName', { ns: 'translation' }) }
  usePageMeta({ title: t(`${page}.title`, brand), description: t(`${page}.pageDescription`, brand) })

  if (!config) {
    return <div className="mx-auto max-w-3xl px-6 py-16 text-slate-500 dark:text-slate-400">{t('loading')}</div>
  }
  const vars = legalVars(config, i18n.language, brand)

  return (
    <article className="mx-auto max-w-3xl px-6 py-16 text-slate-900 dark:text-slate-100">
      {!isProviderConfigured(config) && (
        <p role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {t('notConfigured')}
        </p>
      )}
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">{t(`${page}.title`, brand)}</h1>
      {config.effectiveFrom && <p className="mb-8 text-sm text-slate-500 dark:text-slate-400">{t('effectiveFrom', vars)}</p>}
      <div className="space-y-8">{children(config, vars)}</div>
      <nav className="mt-12 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-200 pt-6 text-sm dark:border-slate-800">
        {(Object.keys(LEGAL_PATHS) as (keyof typeof LEGAL_PATHS)[]).map((key) => (
          <Link key={key} to={LEGAL_PATHS[key]} className="text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300">
            {t(`nav.${key}`)}
          </Link>
        ))}
      </nav>
    </article>
  )
}

/** The sections of one text: a heading, paragraphs and a bulleted list each. */
export function Sections({ sections }: { sections: LegalSection[] }) {
  return (
    <>
      {sections.map((section, i) => (
        <section key={i} className="space-y-3">
          <h2 className="text-lg font-semibold">{section.title}</h2>
          {section.paragraphs?.map((paragraph, j) => (
            <p key={j} className="leading-relaxed text-slate-700 dark:text-slate-300">
              {paragraph}
            </p>
          ))}
          {section.items && (
            <ul className="list-disc space-y-1 pl-6 text-slate-700 dark:text-slate-300">
              {section.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </>
  )
}

/** The sections under a locale key (an array), with the provider's values interpolated; empty when the key is not an array. */
export function useSections(key: string, vars: Record<string, string>): LegalSection[] {
  const { t } = useTranslation('legal')
  const value = t(key, { ...vars, returnObjects: true })
  return Array.isArray(value) ? (value as LegalSection[]) : []
}
