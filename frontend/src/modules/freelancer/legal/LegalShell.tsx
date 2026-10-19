/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../../hooks/usePageMeta'
import type { LegalSection } from '../locales/types'
import { container, mutedText, textLink } from '../ui'
import { useProvider } from './useProvider'

export type LegalKind = 'privacy' | 'terms' | 'cookies'

const DASH = '—'

/**
 * One legal page: its sections from the module's locale bundle, with the
 * provider's details from backend/.env filled into the {{placeholders}} (a
 * value that is not set shows as a dash), a notice while those details are
 * missing, and the other legal pages linked underneath.
 */
export default function LegalShell({ kind }: { kind: LegalKind }) {
  const { t, i18n } = useTranslation('freelancer')
  const provider = useProvider()
  usePageMeta({ title: t(`legal.${kind}.title`), description: t(`legal.${kind}.metaDescription`) })

  const date = provider?.effective_from ? new Date(`${provider.effective_from}T00:00:00`).toLocaleDateString(i18n.resolvedLanguage ?? i18n.language) : ''
  const vars = {
    name: provider?.name || DASH,
    ico: provider?.ico || DASH,
    dic: provider?.dic || DASH,
    address: provider?.address || DASH,
    registration: provider?.registration || DASH,
    email: provider?.email || DASH,
    phone: provider?.phone || DASH,
    dpoEmail: provider?.dpo_email || provider?.email || DASH,
  }
  const sections = t(`legal.${kind}.sections`, { returnObjects: true, ...vars }) as LegalSection[]

  return (
    <article className={`${container} py-12 text-slate-900 dark:text-slate-100 sm:py-16`}>
      {!provider?.configured && (
        <p role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {t('legal.notConfigured')}
        </p>
      )}
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t(`legal.${kind}.title`)}</h1>
      {date && <p className={`mt-3 text-sm ${mutedText}`}>{t('legal.effectiveFrom', { date })}</p>}

      <div className="mt-10 space-y-8">
        {sections.map((section) => (
          <section key={section.title} className="space-y-3">
            <h2 className="text-lg font-semibold">{section.title}</h2>
            {section.paragraphs?.map((paragraph) => (
              <p key={paragraph} className={`leading-relaxed ${mutedText}`}>
                {paragraph}
              </p>
            ))}
            {section.items && (
              <ul className={`list-disc space-y-1 pl-6 ${mutedText}`}>
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>

      <nav className="mt-12 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-200 pt-6 text-sm dark:border-slate-800">
        {(['privacy', 'terms', 'cookies'] as const)
          .filter((other) => other !== kind)
          .map((other) => (
            <Link key={other} to={`/${other}`} className={textLink}>
              {t(`legal.nav.${other}`)}
            </Link>
          ))}
        <Link to="/" className={textLink}>
          {t('legal.backHome')}
        </Link>
      </nav>
    </article>
  )
}
