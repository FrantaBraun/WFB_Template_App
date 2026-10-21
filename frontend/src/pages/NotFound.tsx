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
  usePageMeta({ title: t('notFound.pageTitle'), description: t('notFound.pageDescription')})

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col px-6 text-slate-900 mt-5 dark:text-slate-100 text-center">
      <img src="/notFoundSadPanda.png" width="200" height="300" className='mx-auto my-5'></img>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('notFound.title')}</h1>

      <Link to="/" className="text-slate-900 underline dark:text-slate-100">
          {t('notFound.backToHomePage')}
      </Link>

    </div>
  )
}
