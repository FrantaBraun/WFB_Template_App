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
import { API_BASE, ApiError, CATEGORIES_PATH, fetchJson, useBoardsMe, type Category } from './api'
import BlockedNotice from './BlockedNotice'
import PostForm from './PostForm'
import PostList from './PostList'

/** /categories/:slug - the category's description, the form to add a post (signed in), and its posts by value. */
export default function CategoryPage() {
  const { slug = '' } = useParams()
  const { t } = useTranslation('boards')
  const { user } = useAuth()
  const me = useBoardsMe()
  const [category, setCategory] = useState<Category | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'notFound' | 'error'>('loading')
  // Bumped after a post is published, to start the list over from the top.
  const [listKey, setListKey] = useState(0)

  usePageMeta({ title: category?.title, description: category?.description.slice(0, 200) })

  useEffect(() => {
    let cancelled = false
    setState('loading')
    setCategory(null)
    fetchJson<Category>(`${API_BASE}/categories/${encodeURIComponent(slug)}`)
      .then((found) => {
        if (cancelled) return
        setCategory(found)
        setState('ready')
      })
      .catch((err) => {
        if (!cancelled) setState(err instanceof ApiError && err.status === 404 ? 'notFound' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={CATEGORIES_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('category.back')}
        </Link>
      </p>

      {state === 'loading' && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {state === 'notFound' && <p>{t('category.notFound')}</p>}
      {state === 'error' && <p className="text-red-600 dark:text-red-400">{t('category.loadError')}</p>}

      {state === 'ready' && category && (
        <>
          <header className="mb-8 space-y-3">
            <h1 className="break-words text-3xl font-bold tracking-tight">{category.title}</h1>
            <p className="whitespace-pre-line break-words text-slate-600 dark:text-slate-400">{category.description}</p>
          </header>

          {user && me?.blocked ? (
            <BlockedNotice reason={me.blocked_reason} />
          ) : user ? (
            <PostForm slug={category.slug} onPosted={() => setListKey((key) => key + 1)} />
          ) : (
            <p className="mb-8 rounded-lg border border-slate-200 p-4 text-sm dark:border-slate-800">
              <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
                {t('category.loginToPost')}
              </Link>
            </p>
          )}

          <PostList key={`${category.slug}:${listKey}`} slug={category.slug} />
        </>
      )}
    </div>
  )
}
