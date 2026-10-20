/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import ModuleSlot from '../ModuleSlot'
import { API_BASE, ARTICLES_PATH, fetchJson, formatDate, typeStyle, type ArticleDetail } from './api'
import './articles.css'
import { secondaryButtonClass } from './ui'

/**
 * /articles/:slug - the full article. content is editor HTML the backend
 * sanitized on save. Other modules extend the page through the
 * "article.detail" slot (context: `{ article }`, an ArticleDetail), e.g. a
 * list of the article's dates.
 */
export default function ArticleDetailPage() {
  const { t, i18n } = useTranslation('articles')
  const { slug } = useParams<{ slug: string }>()
  const { user } = useAuth()
  const [article, setArticle] = useState<ArticleDetail | null>(null)
  const [notFound, setNotFound] = useState(false)

  usePageMeta({ title: article?.title, description: article?.perex })

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setArticle(null)
    setNotFound(false)
    fetchJson<ArticleDetail>(`${API_BASE}/${encodeURIComponent(slug)}`)
      .then((a) => !cancelled && setArticle(a))
      .catch(() => !cancelled && setNotFound(true))
    return () => {
      cancelled = true
    }
  }, [slug])

  if (notFound || !article) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-24 text-center text-slate-600 dark:text-slate-400">
        <p>{notFound ? t('detail.notFound') : t('common.loading')}</p>
        {notFound && (
          <Link to={ARTICLES_PATH} className="mt-4 inline-block underline">
            {t('detail.back')}
          </Link>
        )}
      </div>
    )
  }

  const tone = article.type ? 'article-typed' : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'

  return (
    <article className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex items-center justify-between gap-3 text-sm">
        <Link to={ARTICLES_PATH} className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100">
          ← {t('detail.back')}
        </Link>
        {user?.is_admin === true && (
          <Link to={`${ARTICLES_PATH}/manage/${article.id}`} className={secondaryButtonClass}>
            {t('detail.edit')}
          </Link>
        )}
      </div>

      <div style={typeStyle(article.type)} className={`overflow-hidden rounded-2xl border-2 ${tone}`}>
        {article.image_url && <img src={article.image_url} alt="" className="max-h-96 w-full object-cover" />}
        <header className="p-6 pb-2">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            {article.type && <span className="rounded-full border border-current px-2 py-0.5 text-xs font-medium">{article.type.name}</span>}
            {article.pinned && <span aria-label={t('card.pinned')}>📌</span>}
            {article.status === 'archived' && <span className="text-xs">{t('status.archived')}</span>}
            <span>{formatDate(article.created_at, i18n.language)}</span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">{article.title}</h1>
          {article.perex && <p className="mt-3 text-lg text-slate-600 dark:text-slate-300">{article.perex}</p>}
        </header>
        <div className="rich-text-content p-6 pt-2" dangerouslySetInnerHTML={{ __html: article.content }} />
      </div>

      <ModuleSlot name="article.detail" context={{ article }} />
    </article>
  )
}
