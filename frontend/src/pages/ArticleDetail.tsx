/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'

interface ArticleData {
  title: string
  short_description: string
  full_text: string
  event_date: string
}

/** Public route for an Article (/clanek/:slug) - the home page dashboard's
 * teasers and the WYSIWYG editor's @-mention links both point here. Only
 * ever resolves a published article; deliberately doesn't re-check the
 * display window, matching the backend route's own rationale (see
 * app/api/articles/router.py) - the window governs listings, not whether a
 * link someone already has still works. */
export default function ArticleDetail() {
  const { t } = useTranslation()
  const { slug } = useParams<{ slug: string }>()
  const [article, setArticle] = useState<ArticleData | null>(null)
  const [notFound, setNotFound] = useState(false)

  usePageMeta({ title: article?.title, description: article?.short_description })

  useEffect(() => {
    if (!slug) return
    setArticle(null)
    setNotFound(false)
    apiFetch(`/api/articles/${slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setArticle)
      .catch(() => setNotFound(true))
  }, [slug])

  if (notFound) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink dark:text-ink-dark">
        <p className="text-sm text-ink-soft dark:text-ink-soft-dark">{t('articleDetail.notFound')}</p>
      </div>
    )
  }

  if (!article) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink dark:text-ink-dark">
        <p className="text-sm text-ink-soft dark:text-ink-soft-dark">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-ink dark:text-ink-dark">
      <p className="mb-2 text-sm text-ink-muted dark:text-ink-muted-dark">
        {new Date(article.event_date).toLocaleDateString()}
      </p>
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">{article.title}</h1>
      {/* eslint-disable-next-line react/no-danger */}
      <div className="rich-text-content" dangerouslySetInnerHTML={{ __html: article.full_text }} />
    </div>
  )
}
