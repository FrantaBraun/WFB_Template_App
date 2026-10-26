/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import usePageMeta, { absoluteUrl } from '../hooks/usePageMeta'
import CategoriesList from '../modules/boards/CategoriesList'

/** Public landing page: what BumpFeel is, and the categories to read or post in. */
export default function HomePage() {
  const { t, i18n } = useTranslation()
  usePageMeta({
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: t('nav.brand'),
      description: t('meta.description'),
      url: absoluteUrl('/'),
      inLanguage: i18n.resolvedLanguage,
    },
  })

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <header className="mb-10 space-y-3">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t('home.title')}</h1>
        <p className="max-w-xl text-slate-600 dark:text-slate-400">{t('home.description')}</p>
      </header>

      <CategoriesList />
    </div>
  )
}
