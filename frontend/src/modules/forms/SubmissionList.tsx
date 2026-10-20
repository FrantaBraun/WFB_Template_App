/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { formatDateTime, type Submission } from './api'
import { answerText } from './SubmissionView'
import { secondaryButtonClass } from './ui'

const PREVIEW_ANSWERS = 3

/**
 * A table of answers (newest first, as the server sends them): when each was
 * given and a short preview - the first few questions that were shown and
 * answered - with a button to open one in full. Paging is yours: pass
 * `hasMore` and `onLoadMore` to show a "load more" button.
 */
export default function SubmissionList({
  submissions,
  onOpen,
  selectedId,
  hasMore = false,
  onLoadMore,
  loadingMore = false,
}: {
  submissions: Submission[]
  onOpen: (submission: Submission) => void
  selectedId?: string | null
  hasMore?: boolean
  onLoadMore?: () => void
  loadingMore?: boolean
}) {
  const { t, i18n } = useTranslation('forms')

  if (submissions.length === 0) {
    return <p className="text-slate-500 dark:text-slate-400">{t('answers.empty')}</p>
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">{t('answers.when')}</th>
              <th scope="col" className="px-4 py-2 font-medium">{t('answers.preview')}</th>
              <th scope="col" className="px-4 py-2"><span className="sr-only">{t('answers.open')}</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {submissions.map((submission) => {
              const preview = submission.answers
                .filter((entry) => entry.shown && entry.value !== null && entry.value !== undefined)
                .sort((a, b) => a.position - b.position)
                .slice(0, PREVIEW_ANSWERS)
              return (
                <tr key={submission.id} className={submission.id === selectedId ? 'bg-slate-50 dark:bg-slate-800/60' : ''}>
                  <td className="whitespace-nowrap px-4 py-2 align-top text-slate-600 dark:text-slate-300">{formatDateTime(submission.created_at, i18n.language)}</td>
                  <td className="px-4 py-2">
                    {preview.length === 0 ? (
                      <span className="italic text-slate-500 dark:text-slate-400">{t('answers.noAnswers')}</span>
                    ) : (
                      <ul className="space-y-0.5">
                        {preview.map((entry) => (
                          <li key={entry.question_id} className="truncate">
                            <span className="text-slate-500 dark:text-slate-400">{entry.label}: </span>
                            {answerText(entry, i18n.language)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right align-top">
                    <button type="button" onClick={() => onOpen(submission)} className={secondaryButtonClass}>
                      {t('answers.open')}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {hasMore && onLoadMore && (
        <div className="mt-4 text-center">
          <button type="button" onClick={onLoadMore} disabled={loadingMore} className={secondaryButtonClass}>
            {loadingMore ? t('common.loading') : t('answers.loadMore')}
          </button>
        </div>
      )}
    </div>
  )
}
