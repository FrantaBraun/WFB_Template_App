/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { articlePath, typeStyle, type ArticleTeaser } from './api'
import './articles.css'

/**
 * One article as a card linking to its page, framed and tinted in its type's
 * colours (neutral when it has none). Exported for applications that show
 * articles on their own pages (e.g. a home page wall); `meta` adds extra
 * chips next to the type name, such as a date.
 */
export default function ArticleCard({ article, meta }: { article: ArticleTeaser; meta?: ReactNode }) {
  const { t } = useTranslation('articles')
  const tone = article.type
    ? 'article-typed'
    : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'

  return (
    <Link
      to={articlePath(article.slug)}
      style={typeStyle(article.type)}
      className={`flex h-full flex-col overflow-hidden rounded-2xl border-2 text-slate-900 transition-shadow hover:shadow-md dark:text-slate-100 ${tone}`}
    >
      {article.image_url && <img src={article.image_url} alt="" loading="lazy" className="h-44 w-full object-cover" />}
      <div className="flex flex-1 flex-col gap-1 p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          {article.type && <span className="rounded-full border border-current px-2 py-0.5 font-medium">{article.type.name}</span>}
          {article.pinned && <span aria-label={t('card.pinned')}>📌</span>}
          {article.status === 'archived' && <span>{t('status.archived')}</span>}
          {meta}
        </div>
        <h2 className="text-lg font-semibold tracking-tight">{article.title}</h2>
        {article.perex && <p className="text-sm text-slate-600 dark:text-slate-300">{article.perex}</p>}
      </div>
    </Link>
  )
}
