/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import LegalShell, { Sections, useSections } from '../components/LegalShell'
import { localized, type LegalConfig } from '../config/legal'

interface StorageRow {
  name: string
  kind: string
  purpose: string
  duration: string
}

/**
 * Privacy (/privacy): what data is processed, who gets it, how it is secured,
 * who can see what, what the browser storage holds (the application sets no
 * cookies - the table lists every localStorage / sessionStorage key, plus any
 * `extraStorage` the provider adds in public/legal.json), how long data is
 * kept and, while `gdpr` is on in that file, the legal bases and rights. The
 * texts are the `legal` locales' `privacy.*`.
 */
export default function Privacy() {
  return <LegalShell page="privacy">{(config, vars) => <PrivacyBody config={config} vars={vars} />}</LegalShell>
}

function PrivacyBody({ config, vars }: { config: LegalConfig; vars: Record<string, string> }) {
  const { t, i18n } = useTranslation('legal')
  const main = useSections('privacy.sections', vars)
  const storageIntro = useSections('privacy.storage.intro', vars)
  const storageClosing = useSections('privacy.storage.closing', vars)
  const closing = useSections('privacy.closingSections', vars)
  const gdpr = useSections('privacy.gdprSections', vars)

  const builtIn = t('privacy.storage.items', { returnObjects: true })
  const storage: StorageRow[] = [
    ...(Array.isArray(builtIn) ? (builtIn as StorageRow[]) : []),
    ...config.extraStorage.map((item) => ({
      name: item.name,
      kind: '—',
      purpose: localized(item.purpose, i18n.language),
      duration: localized(item.duration, i18n.language),
    })),
  ]

  return (
    <>
      <Sections sections={main} />

      <section className="space-y-6">
        <h2 className="text-2xl font-semibold tracking-tight">{t('privacy.storage.heading')}</h2>
        <Sections sections={storageIntro} />
        <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
              <tr>
                {(['name', 'kind', 'purpose', 'duration'] as const).map((column) => (
                  <th key={column} className="px-4 py-2 font-medium">
                    {t(`privacy.storage.columns.${column}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {storage.map((row) => (
                <tr key={row.name} className="border-t border-slate-200 align-top dark:border-slate-800">
                  <td className="px-4 py-2 font-mono text-xs">{row.name}</td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{row.kind}</td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{row.purpose}</td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{row.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Sections sections={storageClosing} />
      </section>

      <Sections sections={closing} />
      {config.dpoEmail && <p className="text-slate-700 dark:text-slate-300">{t('privacy.dpo', { ...vars, email: config.dpoEmail })}</p>}
      {config.gdpr && <Sections sections={gdpr} />}
    </>
  )
}
