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

interface PageData {
  heading: string
  content: string
}

/** Public route for an admin-authored Page (/stranka/:slug). Only ever
 * resolves a published page - the backend 404s a draft or unknown slug
 * identically. content is sanitized server-side on write (see backend's
 * app/services/sanitize.py), which is what makes rendering it here safe. */
export default function PageDetail() {
  const { t } = useTranslation()
  const { slug } = useParams<{ slug: string }>()
  const [page, setPage] = useState<PageData | null>(null)
  const [notFound, setNotFound] = useState(false)

  usePageMeta({ title: page?.heading })

  useEffect(() => {
    if (!slug) return
    setPage(null)
    setNotFound(false)
    apiFetch(`/api/pages/${slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPage)
      .catch(() => setNotFound(true))
  }, [slug])

  if (notFound) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('pageDetail.notFound')}</p>
      </div>
    )
  }

  if (!page) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">{page.heading}</h1>
      {/* eslint-disable-next-line react/no-danger */}
      <div className="rich-text-content" dangerouslySetInnerHTML={{ __html: page.content }} />
    </div>
  )
}
