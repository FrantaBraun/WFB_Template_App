/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import usePageMeta from '../../hooks/usePageMeta'
import CategoriesList from './CategoriesList'

/** /categories - every category, busiest first. */
export default function CategoriesPage() {
  const { t } = useTranslation('boards')
  usePageMeta({ title: t('list.title') })

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <CategoriesList headingTag="h1" />
    </div>
  )
}
