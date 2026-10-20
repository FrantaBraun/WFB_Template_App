/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { formatDateTime, type Submission, type SubmissionEntry } from './api'

/** An answer as readable text: dates and times in the visitor's format, the rest as the server made it. */
export function answerText(entry: SubmissionEntry, language: string): string {
  if (typeof entry.value === 'string' && entry.type === 'date') return new Date(`${entry.value}T00:00`).toLocaleDateString(language)
  if (typeof entry.value === 'string' && entry.type === 'datetime') return new Date(entry.value).toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' })
  return entry.display
}

/**
 * One answer in full, readable: each question as it was worded when answered
 * with what was answered (an option by its label); a question that was never
 * shown (its conditions did not hold) is greyed out as "not shown", one that
 * was shown but left blank says "no answer".
 */
export default function SubmissionView({ submission }: { submission: Submission }) {
  const { t, i18n } = useTranslation('forms')
  const entries = [...submission.answers].sort((a, b) => a.position - b.position)

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">{formatDateTime(submission.created_at, i18n.language)}</p>
      <dl className="space-y-4">
        {entries.map((entry) => (
          <div key={entry.question_id} className={entry.shown ? '' : 'opacity-60'}>
            <dt className="text-sm font-medium text-slate-700 dark:text-slate-300">{entry.label}</dt>
            <dd className="mt-0.5 whitespace-pre-wrap text-slate-900 dark:text-slate-100">
              {!entry.shown ? (
                <span className="italic text-slate-500 dark:text-slate-400">{t('answers.notShown')}</span>
              ) : entry.value === null || entry.value === undefined ? (
                <span className="italic text-slate-500 dark:text-slate-400">{t('answers.noAnswer')}</span>
              ) : (
                answerText(entry, i18n.language)
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
