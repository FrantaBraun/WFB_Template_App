/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'

/**
 * Sitewide footer, styled after the one on withfbraun.com - a border-topped,
 * centered, muted credit line. Rendered by Layout below every page's content.
 */
export default function Footer() {
  const { t } = useTranslation()

  return (
    <footer className="border-t border-slate-200 px-6 py-8 text-center text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
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
