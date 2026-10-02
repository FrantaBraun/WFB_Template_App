/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  ApiError,
  CATEGORIES_PATH,
  CATEGORY_DESCRIPTION_MAX,
  CATEGORY_TITLE_MAX,
  categoryPath,
  charCount,
  postJson,
  type Category,
} from './api'
import { Counter } from './PostForm'

/** /categories/new - a signed-in user creates a category: a title (its address is generated from it) and a short description. */
export default function NewCategoryPage() {
  const { t } = useTranslation('boards')
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [errorKey, setErrorKey] = useState<string | null>(null)

  usePageMeta({ title: t('newCategory.title') })

  const titleLength = charCount(title)
  const descriptionLength = charCount(description)
  const valid =
    titleLength > 0 &&
    titleLength <= CATEGORY_TITLE_MAX &&
    descriptionLength > 0 &&
    descriptionLength <= CATEGORY_DESCRIPTION_MAX

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid || busy) return
    setBusy(true)
    setErrorKey(null)
    try {
      const category = await postJson<Category>(`${API_BASE}/categories`, { title, description })
      navigate(categoryPath(category.slug))
    } catch (err) {
      setErrorKey(err instanceof ApiError && err.status === 422 ? 'newCategory.invalid' : 'newCategory.error')
      setBusy(false)
    }
  }

  const input =
    'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={CATEGORIES_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('category.back')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-bold tracking-tight">{t('newCategory.title')}</h1>

      {loading ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : !user ? (
        <p>
          <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
            {t('newCategory.loginRequired')}
          </Link>
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="category-title" className="mb-1 block text-sm font-medium">
              {t('newCategory.name')}
            </label>
            <input id="category-title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
            <div className="mt-1 flex justify-between gap-2 text-xs">
              <span className="text-slate-500 dark:text-slate-400">{t('newCategory.nameHint')}</span>
              <Counter count={titleLength} max={CATEGORY_TITLE_MAX} />
            </div>
          </div>

          <div>
            <label htmlFor="category-description" className="mb-1 block text-sm font-medium">
              {t('newCategory.description')}
            </label>
            <textarea
              id="category-description"
              rows={8}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={input}
            />
            <div className="mt-1 text-right text-xs">
              <Counter count={descriptionLength} max={CATEGORY_DESCRIPTION_MAX} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={!valid || busy}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {busy ? t('newCategory.creating') : t('newCategory.create')}
            </button>
            {errorKey && (
              <span role="alert" className="text-sm text-red-600 dark:text-red-400">
                {t(errorKey)}
              </span>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
