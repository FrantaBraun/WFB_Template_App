/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useEnabledModules } from '../modules/registry'

/**
 * Sitewide footer, styled after the one on withfbraun.com - a border-topped,
 * centered, muted credit line. Rendered by Layout below every page's content.
 * Enabled modules' footerLinks (e.g. legal pages) render as a link row above
 * the credit line; the footer resolves enabled modules itself (the hook is
 * cached) so Layout doesn't have to thread them through.
 */
export default function Footer() {
  const { t } = useTranslation()
  const footerLinks = useEnabledModules().flatMap((module) => module.footerLinks ?? [])

  return (
    <footer className="border-t border-slate-200 px-6 py-8 text-center text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
      {footerLinks.length > 0 && (
        <nav className="mb-3 flex flex-wrap justify-center gap-x-4 gap-y-1">
          {footerLinks.map((item) => (
            <Link key={item.to} to={item.to} className="hover:text-slate-600 dark:hover:text-slate-300">
              {t(item.labelKey)}
            </Link>
          ))}
        </nav>
      )}
      <p>
        <a
          href="https://withfbraun.com"
          target="_blank"
          rel="noreferrer"
          className="font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300"
        >
          {t('footer.ecosystem')}
        </a>
        <span className="mx-2">·</span>
        {t('footer.copyright', { year: new Date().getFullYear() })}
      </p>
    </footer>
  )
}
