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
    <footer className="border-t border-ink/10 px-6 py-8 text-center text-sm text-ink-muted dark:border-ink-dark/10 dark:text-ink-muted-dark">
      <p>
        <a
          href="https://withfbraun.com"
          target="_blank"
          rel="noreferrer"
          className="font-medium text-teal hover:text-teal-dark dark:text-teal-dark dark:hover:text-teal"
        >
          {t('footer.ecosystem')}
        </a>
        <span className="mx-2">·</span>
        {t('footer.copyright', { year: new Date().getFullYear() })}
      </p>
    </footer>
  )
}
