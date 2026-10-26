/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import usePageMeta, { absoluteUrl } from '../../hooks/usePageMeta'
import { CATEGORIES_PATH } from './api'
import CategoriesList from './CategoriesList'

/**
 * /categories - every category, busiest first, with a search. The search
 * text lives in the address (`?q=`), so a search can be shared and survives a
 * reload. A page of search results is kept out of search engines (the
 * canonical address, which usePageMeta takes without the query, is the list).
 */
export default function CategoriesPage() {
  const { t } = useTranslation('boards')
  const { t: tCore } = useTranslation()
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''

  usePageMeta({
    title: t('list.title'),
    description: t('list.description'),
    noindex: query.trim() !== '',
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: tCore('common.home'), item: absoluteUrl('/') },
        { '@type': 'ListItem', position: 2, name: t('list.title'), item: absoluteUrl(CATEGORIES_PATH) },
      ],
    },
  })

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <CategoriesList
        headingTag="h1"
        query={query}
        onQueryChange={(next) => setParams(next ? { q: next } : {}, { replace: true })}
      />
    </div>
  )
}
