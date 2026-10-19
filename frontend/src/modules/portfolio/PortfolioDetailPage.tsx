/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  PORTFOLIO_PATH,
  errorStatus,
  fetchJson,
  isWebUrl,
  metaText,
  paragraphsOf,
  usePublicLanguage,
  type PublicItemDetail,
} from './api'
import { BackLink, StatusBadge, TagList, accentButtonClass, container, mutedText, secondaryButtonClass } from './ui'

type State = { status: 'loading' } | { status: 'notFound' } | { status: 'error' } | { status: 'ready'; item: PublicItemDetail }

/** /portfolio/:slug - one published project: its description, tags and a link to open it. */
export default function PortfolioDetailPage() {
  const { t } = useTranslation('portfolio')
  const { slug } = useParams<{ slug: string }>()
  const language = usePublicLanguage()
  const [state, setState] = useState<State>({ status: 'loading' })
  const [reload, setReload] = useState(0)

  const item = state.status === 'ready' ? state.item : null
  usePageMeta({
    title: item?.title ?? (state.status === 'notFound' ? t('detail.notFoundTitle') : undefined),
    description: item ? metaText(item.summary) : undefined,
    noindex: state.status === 'notFound',
  })

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    // Another project replaces the page at once; the same one in another language stays up until the new text arrives.
    setState((current) => (current.status === 'ready' && current.item.slug === slug ? current : { status: 'loading' }))
    fetchJson<PublicItemDetail>(`${API_BASE}/items/${encodeURIComponent(slug)}?language=${encodeURIComponent(language)}`)
      .then((found) => !cancelled && setState({ status: 'ready', item: found }))
      .catch((error) => !cancelled && setState({ status: errorStatus(error) === 404 ? 'notFound' : 'error' }))
    return () => {
      cancelled = true
    }
  }, [slug, language, reload])

  if (state.status === 'loading') {
    return (
      <div className={`${container} py-16`}>
        <p role="status" className={mutedText}>{t('common.loading')}</p>
      </div>
    )
  }

  if (state.status !== 'ready') {
    const notFound = state.status === 'notFound'
    return (
      <div className={`${container} space-y-4 py-16 text-slate-900 dark:text-slate-100`}>
        {notFound && <h1 className="text-2xl font-semibold tracking-tight">{t('detail.notFoundTitle')}</h1>}
        <p role={notFound ? undefined : 'alert'} className={notFound ? mutedText : 'text-red-700 dark:text-red-400'}>
          {t(notFound ? 'detail.notFound' : 'detail.loadError')}
        </p>
        <div className="flex flex-wrap items-center gap-4">
          {!notFound && (
            <button type="button" onClick={() => setReload((n) => n + 1)} className={secondaryButtonClass}>
              {t('common.retry')}
            </button>
          )}
          <BackLink to={PORTFOLIO_PATH}>{t('detail.back')}</BackLink>
        </div>
      </div>
    )
  }

  const { title, summary, description, url, status, tags } = state.item
  const paragraphs = paragraphsOf(description)

  return (
    <article className={`${container} py-12 text-slate-900 dark:text-slate-100 sm:py-16`}>
      <BackLink to={PORTFOLIO_PATH}>{t('detail.back')}</BackLink>

      <div className="mt-6 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <h1 className="min-w-0 break-words text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <StatusBadge status={status} />
      </div>

      <p className={`mt-4 max-w-2xl break-words text-lg ${mutedText}`}>{summary}</p>

      {paragraphs.length > 0 && (
        <div className="mt-8 max-w-2xl space-y-4">
          {paragraphs.map((paragraph, index) => (
            <p key={index} className="whitespace-pre-line break-words">
              {paragraph}
            </p>
          ))}
        </div>
      )}

      {tags.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('detail.tagsLabel')}
          </h2>
          <TagList tags={tags} label={t('detail.tagsLabel')} />
        </div>
      )}

      {isWebUrl(url) && (
        <div className="mt-10">
          <a href={url} target="_blank" rel="noopener noreferrer" className={accentButtonClass}>
            {t('detail.open')}
            <span className="sr-only"> {t('detail.opensInNewTab')}</span>
            <span aria-hidden="true" className="ml-2">↗</span>
          </a>
        </div>
      )}
    </article>
  )
}
