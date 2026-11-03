/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import LegalShell, { Sections, useSections } from '../components/LegalShell'
import type { LegalConfig } from '../config/legal'

/**
 * The full description of the application (/about): what it does, in which
 * formats, how versions, comparison, search, teams and alerts work and what it
 * cannot do yet - plus who runs it, from public/legal.json. The texts are the
 * `legal` locales' `about.*`.
 */
export default function About() {
  return <LegalShell page="about">{(config, vars) => <AboutBody config={config} vars={vars} />}</LegalShell>
}

function AboutBody({ config, vars }: { config: LegalConfig; vars: Record<string, string> }) {
  const { t } = useTranslation('legal')
  const sections = useSections('about.sections', vars)
  const closing = useSections('about.closingSections', vars)
  const rows: [string, ReactNode][] = [
    ['name', vars.name],
    ['ico', vars.ico],
    ...(config.provider.dic ? ([['dic', vars.dic]] as [string, ReactNode][]) : []),
    ['address', vars.address],
    ['registration', vars.registration],
    ['email', config.provider.email ? <a href={`mailto:${config.provider.email}`} className="underline">{vars.email}</a> : vars.email],
    ['phone', config.provider.phone ? <a href={`tel:${config.provider.phone.replace(/\s/g, '')}`} className="underline">{vars.phone}</a> : vars.phone],
  ]

  return (
    <>
      <Sections sections={sections} />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t('provider.heading', vars)}</h2>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-2xl border border-slate-200 bg-white p-6 text-sm sm:grid-cols-[auto_1fr] dark:border-slate-800 dark:bg-slate-900">
          {rows.map(([field, value]) => (
            <div key={field} className="contents">
              <dt className="text-slate-500 dark:text-slate-400">{t(`provider.fields.${field}`)}</dt>
              <dd className="mb-2 sm:mb-0">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Sections sections={closing} />
    </>
  )
}
