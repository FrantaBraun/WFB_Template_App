/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { RULES_PATH, type Assessment, type Finding, type Level, type Score } from './api'

/**
 * The verdict of the content checks on a draft, shown before it is
 * published: what the overall level means for the author, the two scores
 * with their levels, and the specific aspects behind them (a translated
 * reason per finding, with the words it was found in). `children` are the
 * actions the level allows - "publish anyway", "edit".
 */
export default function AssessmentPanel({
  assessment,
  subject,
  children,
}: {
  assessment: Assessment
  subject: 'post' | 'category'
  children?: ReactNode
}) {
  const { t } = useTranslation('boards')
  const blocked = assessment.level === 'blocked'

  return (
    <section
      role="alert"
      className={`rounded-lg border p-4 text-sm ${
        blocked ? 'border-red-600 dark:border-red-400' : 'border-slate-400 dark:border-slate-500'
      }`}
    >
      <h3 className={`font-semibold ${blocked ? 'text-red-600 dark:text-red-400' : ''}`}>
        {t(`moderation.${assessment.level}.${subject}`)}
      </h3>

      <ul className="mt-2 space-y-1">
        <ScoreLine label={t('moderation.violationScore')} score={assessment.violation} />
        {assessment.topic && <ScoreLine label={t('moderation.topicScore')} score={assessment.topic} />}
      </ul>

      {assessment.findings.length > 0 && (
        <div className="mt-3">
          <p className="font-medium">{t('moderation.why')}</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {assessment.findings.map((finding, index) => (
              <FindingLine key={`${finding.code}-${index}`} finding={finding} />
            ))}
          </ul>
        </div>
      )}

      <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
        <Trans
          t={t}
          i18nKey="moderation.seeRules"
          components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
        />
      </p>

      {children && <div className="mt-4 flex flex-wrap gap-3">{children}</div>}
    </section>
  )
}

function ScoreLine({ label, score }: { label: string; score: Score }) {
  const { t } = useTranslation('boards')
  return (
    <li className="flex flex-wrap gap-x-2">
      <span>{label}:</span>
      <strong>{score.percent} %</strong>
      <span className="text-slate-600 dark:text-slate-400">({t(`moderation.levelName.${score.level as Level}`)})</span>
    </li>
  )
}

function FindingLine({ finding }: { finding: Finding }) {
  const { t } = useTranslation('boards')
  const label = t(`moderation.finding.${finding.code}`, { defaultValue: t('moderation.finding.unknown') })
  const hint = finding.aspect === 'topic' ? t('moderation.categoryIsAbout') : t('moderation.foundIn')
  return (
    <li>
      {label}
      {finding.matches.length > 0 && (
        <span className="text-slate-600 dark:text-slate-400">
          {' '}
          — {hint}: {finding.matches.map((match) => `“${match}”`).join(', ')}
        </span>
      )}
    </li>
  )
}
