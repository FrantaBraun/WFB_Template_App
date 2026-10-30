/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../hooks/usePageMeta'


export default function NotFound() {
  const { t } = useTranslation()
  // The server answers 200 for every unknown address (the SPA's index.html), so
  // this page is a soft 404 to a crawler; noindex is how Google asks an SPA to
  // keep its error views out of the index.
  usePageMeta({ title: t('notFound.pageTitle'), description: t('notFound.pageDescription'), noindex: true })

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col px-6 text-slate-900 mt-5 dark:text-slate-100 text-center">
      <img src="/notFoundSadPanda.png" alt="" width="200" height="300" className='mx-auto my-5'></img>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('notFound.title')}</h1>

      <Link to="/" className="text-slate-900 underline dark:text-slate-100">
          {t('notFound.backToHomePage')}
      </Link>

    </div>
  )
}
