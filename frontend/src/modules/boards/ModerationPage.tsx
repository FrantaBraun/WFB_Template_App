/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import { CATEGORIES_PATH, useBoardsMe } from './api'
import ModerationAccounts from './ModerationAccounts'
import ModerationCategories from './ModerationCategories'
import ModerationPosts from './ModerationPosts'
import ModerationRules from './ModerationRules'

type Tab = 'posts' | 'categories' | 'rules' | 'accounts'
const TABS: Tab[] = ['posts', 'categories', 'rules', 'accounts']

/**
 * /moderation - this application's administrators: find and block posts,
 * block or restore categories, edit a category's machine rules, lift account
 * blocks. Anyone else sees
 * only that they may not be here (the endpoints refuse them anyway). The
 * category being edited lives in the URL (?rules=<slug>), so a post's "edit
 * the category's rules" link and a reload both land on the same editor.
 */
export default function ModerationPage() {
  const { t } = useTranslation('boards')
  const { user, loading } = useAuth()
  const me = useBoardsMe()
  const [params, setParams] = useSearchParams()
  const ruleSlug = params.get('rules') ?? ''
  const [tab, setTab] = useState<Tab>(ruleSlug ? 'rules' : 'posts')

  usePageMeta({ title: t('admin.title') })

  function editRules(slug: string) {
    setParams(slug ? { rules: slug } : {}, { replace: true })
    setTab('rules')
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={CATEGORIES_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('category.back')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-bold tracking-tight">{t('admin.title')}</h1>

      {loading || (user && me === null) ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : !user ? (
        <p>
          <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
            {t('admin.loginRequired')}
          </Link>
        </p>
      ) : !me?.is_admin ? (
        <p>{t('admin.forbidden')}</p>
      ) : (
        <>
          <div role="tablist" className="mb-6 flex gap-4 border-b border-slate-200 dark:border-slate-800">
            {TABS.map((name) => (
              <button
                key={name}
                role="tab"
                type="button"
                aria-selected={tab === name}
                onClick={() => setTab(name)}
                className={`-mb-px border-b-2 px-1 pb-2 ${
                  tab === name ? 'border-slate-900 font-semibold dark:border-slate-100' : 'border-transparent text-slate-500 dark:text-slate-400'
                }`}
              >
                {t(`admin.tabs.${name}`)}
              </button>
            ))}
          </div>

          {tab === 'posts' && <ModerationPosts onEditRules={editRules} />}
          {tab === 'categories' && <ModerationCategories onEditRules={editRules} />}
          {tab === 'rules' && <ModerationRules slug={ruleSlug} onSlugChange={editRules} />}
          {tab === 'accounts' && <ModerationAccounts />}
        </>
      )}
    </div>
  )
}
