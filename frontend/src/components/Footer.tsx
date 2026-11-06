/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { LEGAL_PATHS } from './LegalShell'
import { useEnabledModules } from '../modules/registry'

/**
 * Sitewide footer, styled after the one on withfbraun.com - a border-topped,
 * centered, muted credit line. Rendered by Layout below every page's content.
 * The About, Terms and Privacy pages are linked from every page, followed by
 * enabled modules' footerLinks, as one link row above the credit line; the footer resolves enabled modules itself (the hook is
 * cached) so Layout doesn't have to thread them through.
 */
export default function Footer() {
  const { t } = useTranslation()
  const footerLinks = [
    ...(Object.keys(LEGAL_PATHS) as (keyof typeof LEGAL_PATHS)[]).map((key) => ({ to: LEGAL_PATHS[key], labelKey: `legal:nav.${key}` })),
    ...useEnabledModules().flatMap((module) => module.footerLinks ?? []),
  ]

  return (
    <footer className="border-t border-slate-300 px-6 py-8 text-center text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
      {footerLinks.length > 0 && (
        <nav className="mb-3 flex flex-wrap justify-center gap-x-4 gap-y-1">
          {footerLinks.map((item) => (
            <Link key={item.to} to={item.to} className="hover:text-slate-600 dark:hover:text-slate-300">
              {t(item.labelKey)}
            </Link>
          ))}
        </nav>
      )}
      <p className="flex flex-wrap items-center justify-center gap-1">
        <span className="font-semibold text-slate-500 dark:text-slate-400">WFB</span>
        <span className="text-2xl mx-1">·</span>
        {t('footer.copyright', { year: new Date().getFullYear() })}
      </p>
    </footer>
  )
}
