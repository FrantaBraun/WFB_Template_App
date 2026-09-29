/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The legal pages a site taking online payments must publish: About (the
// provider's identification), Terms and conditions, Privacy (GDPR) and
// Cookies. Every text lives in this module's locales (legalLocales.ts) as
// sections interpolated with the provider details from public/legal.json -
// see the module README for what each page must contain and why.
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { isProviderConfigured, legalVars, localized, useLegalConfig, type LegalConfig } from './legal'

export const LEGAL_PATHS = {
  about: '/o-nas',
  terms: '/obchodni-podminky',
  privacy: '/ochrana-osobnich-udaju',
  cookies: '/cookies',
} as const

interface Section {
  title: string
  paragraphs?: string[]
  items?: string[]
}

const NS = 'stripe_payment_gate'

/** Shared chrome + data loading for every legal page. */
function LegalShell({ titleKey, children }: { titleKey: string; children: (config: LegalConfig, vars: Record<string, string>) => ReactNode }) {
  const { t, i18n } = useTranslation(NS)
  const config = useLegalConfig()
  usePageMeta({ title: t(titleKey) })

  if (!config) {
    return <div className="mx-auto max-w-3xl px-6 py-16 text-slate-500 dark:text-slate-400">{t('legal.loading')}</div>
  }
  const vars = legalVars(config, i18n.language, t)

  return (
    <article className="mx-auto max-w-3xl px-6 py-16 text-slate-900 dark:text-slate-100">
      {!isProviderConfigured(config) && (
        <p role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {t('legal.notConfigured')}
        </p>
      )}
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">{t(titleKey)}</h1>
      {config.effectiveFrom && (
        <p className="mb-8 text-sm text-slate-500 dark:text-slate-400">{t('legal.effectiveFrom', vars)}</p>
      )}
      <div className="space-y-8">{children(config, vars)}</div>
      <LegalNav />
    </article>
  )
}

function Sections({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections.map((section, i) => (
        <section key={i} className="space-y-3">
          <h2 className="text-lg font-semibold">{section.title}</h2>
          {section.paragraphs?.map((p, j) => (
            <p key={j} className="leading-relaxed text-slate-700 dark:text-slate-300">{p}</p>
          ))}
          {section.items && (
            <ul className="list-disc space-y-1 pl-6 text-slate-700 dark:text-slate-300">
              {section.items.map((item, j) => <li key={j}>{item}</li>)}
            </ul>
          )}
        </section>
      ))}
    </>
  )
}

/** Cross-links between the four legal pages, at the bottom of each. */
function LegalNav() {
  const { t } = useTranslation(NS)
  const links: [string, string][] = [
    [LEGAL_PATHS.about, 'legal.about.title'],
    [LEGAL_PATHS.terms, 'legal.terms.title'],
    [LEGAL_PATHS.privacy, 'legal.privacy.title'],
    [LEGAL_PATHS.cookies, 'legal.cookies.title'],
  ]
  return (
    <nav className="mt-12 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-200 pt-6 text-sm dark:border-slate-800">
      {links.map(([to, key]) => (
        <Link key={to} to={to} className="text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300">
          {t(key)}
        </Link>
      ))}
    </nav>
  )
}

function useSections(key: string, vars: Record<string, string>): Section[] {
  const { t } = useTranslation(NS)
  const value = t(key, { ...vars, returnObjects: true })
  return Array.isArray(value) ? (value as Section[]) : []
}

export function AboutPage() {
  return <LegalShell titleKey="legal.about.title">{(config, vars) => <AboutBody config={config} vars={vars} />}</LegalShell>
}

function AboutBody({ config, vars }: { config: LegalConfig; vars: Record<string, string> }) {
  const { t } = useTranslation(NS)
  const sections = useSections('legal.about.sections', vars)
  const rows: [string, ReactNode][] = [
    ['legal.about.fields.name', vars.name],
    ['legal.about.fields.ico', vars.ico],
    ...(config.provider.dic ? ([['legal.about.fields.dic', vars.dic]] as [string, ReactNode][]) : []),
    ['legal.about.fields.vat', vars.vatStatement],
    ['legal.about.fields.address', vars.address],
    ['legal.about.fields.registration', vars.registration],
    ['legal.about.fields.email', config.provider.email ? <a href={`mailto:${config.provider.email}`} className="underline">{vars.email}</a> : vars.email],
    ['legal.about.fields.phone', config.provider.phone ? <a href={`tel:${config.provider.phone.replace(/\s/g, '')}`} className="underline">{vars.phone}</a> : vars.phone],
  ]
  return (
    <>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t('legal.about.providerHeading')}</h2>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-2xl border border-slate-200 bg-white p-6 text-sm sm:grid-cols-[auto_1fr] dark:border-slate-800 dark:bg-slate-900">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-slate-500 dark:text-slate-400">{t(label)}</dt>
              <dd className="mb-2 sm:mb-0">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Sections sections={sections} />
    </>
  )
}

export function TermsPage() {
  return <LegalShell titleKey="legal.terms.title">{(_, vars) => <TermsBody vars={vars} />}</LegalShell>
}

function TermsBody({ vars }: { vars: Record<string, string> }) {
  return <Sections sections={useSections('legal.terms.sections', vars)} />
}

export function PrivacyPage() {
  return <LegalShell titleKey="legal.privacy.title">{(config, vars) => <PrivacyBody config={config} vars={vars} />}</LegalShell>
}

function PrivacyBody({ config, vars }: { config: LegalConfig; vars: Record<string, string> }) {
  const { t } = useTranslation(NS)
  const common = useSections('legal.privacy.sections', vars)
  const gdpr = useSections('legal.privacy.gdprSections', vars)
  return (
    <>
      <Sections sections={common} />
      {config.dpoEmail && (
        <p className="text-slate-700 dark:text-slate-300">{t('legal.privacy.dpo', { email: config.dpoEmail })}</p>
      )}
      {config.gdpr && <Sections sections={gdpr} />}
    </>
  )
}

export function CookiesPage() {
  return <LegalShell titleKey="legal.cookies.title">{(config, vars) => <CookiesBody config={config} vars={vars} />}</LegalShell>
}

function CookiesBody({ config, vars }: { config: LegalConfig; vars: Record<string, string> }) {
  const { t, i18n } = useTranslation(NS)
  const intro = useSections('legal.cookies.sections', vars)
  const outro = useSections('legal.cookies.closingSections', vars)
  const builtIn = t('legal.cookies.storage', { returnObjects: true })
  const storage = [
    ...(Array.isArray(builtIn) ? (builtIn as { name: string; purpose: string; duration: string }[]) : []),
    ...config.extraStorage.map((item) => ({
      name: item.name,
      purpose: localized(item.purpose, i18n.language),
      duration: localized(item.duration, i18n.language),
    })),
  ]
  return (
    <>
      <Sections sections={intro} />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t('legal.cookies.tableHeading')}</h2>
        <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">{t('legal.cookies.columns.name')}</th>
                <th className="px-4 py-2 font-medium">{t('legal.cookies.columns.purpose')}</th>
                <th className="px-4 py-2 font-medium">{t('legal.cookies.columns.duration')}</th>
              </tr>
            </thead>
            <tbody>
              {storage.map((item) => (
                <tr key={item.name} className="border-t border-slate-200 align-top dark:border-slate-800">
                  <td className="px-4 py-2 font-mono text-xs">{item.name}</td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{item.purpose}</td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{item.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Sections sections={outro} />
    </>
  )
}
