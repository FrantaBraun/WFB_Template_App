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
import { API_BASE, ApiError, CATEGORIES_PATH, fetchJson, useBoardsMe, type Category, type Post } from './api'
import BlockedNotice from './BlockedNotice'
import BoostPanel from './BoostPanel'
import PostForm from './PostForm'
import PostList from './PostList'
import { card, chip, primaryButton, secondaryButton } from './styles'

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
  // The post just published, while the offer to raise its value is open.
  const [fresh, setFresh] = useState<Post | null>(null)
  const [showForm, setShowForm] = useState(false)

  usePageMeta({ title: category?.title, description: category?.description.slice(0, 200) })

  useEffect(() => {
    if (showForm && user) {
      const postForm = document.getElementById('post-form');
      if (postForm) postForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const postTitle = document.getElementById('post-title');
      if (postTitle) postTitle.focus();
    }
  }, [showForm, user]);

  useEffect(() => {
    let cancelled = false
    setState('loading')
    setCategory(null)
    setFresh(null)
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
          <header className="mb-8 rounded-3xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-amber-50 p-6 shadow-sm sm:p-8 dark:border-violet-500/30 dark:from-violet-500/15 dark:via-slate-900 dark:to-amber-500/10">
            <p className="mb-2 text-xs font-bold uppercase tracking-widest text-violet-700 dark:text-violet-300">
              <span aria-hidden="true">🏆</span> {t('category.kicker')}
            </p>
            <h1 className="break-words text-3xl font-extrabold tracking-tight sm:text-4xl">{category.title}</h1>
            <p className="mt-3 whitespace-pre-line break-words text-slate-600 dark:text-slate-300">{category.description}</p>
            <p className="mt-4">
              <span className={chip}>{t('list.posts', { count: category.post_count })}</span>
            </p>
          </header>

          {user && me?.blocked ? (
            <BlockedNotice reason={me.blocked_reason} />
          ) : user ? (
            showForm ? (
              <>
                <div className='text-right'>
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className={`mb-4 ${secondaryButton}`}
                  >
                    {'❌'}
                  </button>
                </div>
                <PostForm
                  slug={category.slug}
                  onPosted={(post) => {
                    setFresh(post)
                    setListKey((key) => key + 1)
                  }}
                />
                <div className='text-right'>
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className={`mb-4 ${secondaryButton}`}
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              </>
            ) : (
              <div className='text-center'>
                <button
                  type="button"
                  onClick={() => setShowForm(true)}
                  className={`mb-8 ${primaryButton}`}
                >
                  {t('category.addPost')}
                </button>
              </div>
            )
          ) : (
            <p className={`mb-8 p-4 text-sm ${card}`}>
              <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
                {t('category.loginToPost')}
              </Link>
            </p>
          )}

          {fresh && <BoostPanel post={fresh} intro={t('boost.published', { title: fresh.title })} onClose={() => setFresh(null)} />}

          <PostList key={`${category.slug}:${listKey}`} slug={category.slug} />
          {!showForm && user && !me?.blocked && (
            <div className='text-center'>
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className={`mt-8 ${primaryButton}`}
              >
                {t('category.addPost')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
