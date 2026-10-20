/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import type { Question } from './api'
import { inputClass } from './ui'
import { shownQuestions, type FormValues } from './values'

interface FormRendererProps {
  questions: Question[]
  values: FormValues
  onChange: (values: FormValues) => void
  /** Error codes from the server (or your own checks), by question id: shown under the question in the visitor's language. */
  errors?: Record<string, string>
  disabled?: boolean
  /** Distinguishes two forms on one page. */
  idPrefix?: string
}

/** The strictest limit the server enforces on a text answer, whatever the question says. */
const MAX_TEXT_LENGTH = 2000

function QuestionControl({
  question,
  value,
  onChange,
  disabled,
  inputId,
  describedBy,
}: {
  question: Question
  value: string | string[] | undefined
  onChange: (value: string | string[]) => void
  disabled: boolean
  inputId: string
  describedBy: string | undefined
}) {
  const { t } = useTranslation('forms')
  const { config } = question
  const common = { id: inputId, disabled, 'aria-describedby': describedBy, className: inputClass }
  const text = typeof value === 'string' ? value : ''

  switch (question.type) {
    case 'text':
      return config.multiline ? (
        <textarea
          {...common}
          rows={4}
          required={question.required}
          maxLength={Math.min(config.max_length ?? MAX_TEXT_LENGTH, MAX_TEXT_LENGTH)}
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          {...common}
          type="text"
          required={question.required}
          maxLength={Math.min(config.max_length ?? MAX_TEXT_LENGTH, MAX_TEXT_LENGTH)}
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'number':
      return (
        <input
          {...common}
          type="number"
          inputMode={config.kind === 'decimal' ? 'decimal' : 'numeric'}
          step={config.kind === 'decimal' ? 'any' : 1}
          min={typeof config.min === 'number' ? config.min : undefined}
          max={typeof config.max === 'number' ? config.max : undefined}
          required={question.required}
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'date':
    case 'time':
    case 'datetime':
      return (
        <input
          {...common}
          type={question.type === 'datetime' ? 'datetime-local' : question.type}
          min={typeof config.min === 'string' ? config.min : undefined}
          max={typeof config.max === 'string' ? config.max : undefined}
          required={question.required}
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'radio':
      return (
        <div role="radiogroup" aria-labelledby={`${inputId}-label`} aria-describedby={describedBy} className="space-y-1.5">
          {(config.options ?? []).map((option) => (
            <label key={option.id} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={inputId}
                value={option.id}
                checked={text === option.id}
                disabled={disabled}
                onChange={() => onChange(option.id)}
              />
              {option.label}
            </label>
          ))}
          {!question.required && text !== '' && (
            <button type="button" disabled={disabled} onClick={() => onChange('')} className="text-xs text-slate-500 underline dark:text-slate-400">
              {t('renderer.clearChoice')}
            </button>
          )}
        </div>
      )
    case 'checkbox': {
      const chosen = Array.isArray(value) ? value : []
      return (
        <div role="group" aria-labelledby={`${inputId}-label`} aria-describedby={describedBy} className="space-y-1.5">
          {(config.options ?? []).map((option) => (
            <label key={option.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                value={option.id}
                checked={chosen.includes(option.id)}
                disabled={disabled}
                onChange={(e) => onChange(e.target.checked ? [...chosen, option.id] : chosen.filter((id) => id !== option.id))}
              />
              {option.label}
            </label>
          ))}
          {(config.min_select ?? 0) > 0 || config.max_select ? (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('renderer.selectRange', { min: Math.max(config.min_select ?? 0, question.required ? 1 : 0), max: config.max_select ?? (config.options ?? []).length })}
            </p>
          ) : null}
        </div>
      )
    }
  }
}

/**
 * The visitor's form: draws the questions of `questions` that the conditions
 * show for the answers so far (a question appears and disappears as the visitor
 * answers the ones before it), keeps the values in the `values` / `onChange` you
 * hold, and shows `errors` under the questions they belong to. It does not
 * submit anything: use collectAnswers(questions, values) (values.ts) to get
 * what to send - only the shown, answered questions, numbers as numbers - and
 * pass the server's error codes back in `errors`. Checking the answers is the
 * server's job; the inputs only carry the obvious limits (required, number
 * and date bounds, maximum length).
 */
export default function FormRenderer({ questions, values, onChange, errors = {}, disabled = false, idPrefix = 'form' }: FormRendererProps) {
  const { t } = useTranslation('forms')
  const shown = shownQuestions(questions, values)

  return (
    <div className="space-y-5">
      {shown.map((question) => {
        const inputId = `${idPrefix}-${question.id}`
        const error = errors[question.id]
        const describedBy = [question.help_text ? `${inputId}-help` : null, error ? `${inputId}-error` : null].filter(Boolean).join(' ') || undefined
        const isGroup = question.type === 'radio' || question.type === 'checkbox'
        return (
          <div key={question.id}>
            {isGroup ? (
              <span id={`${inputId}-label`} className="mb-1 block text-sm font-medium text-slate-800 dark:text-slate-200">
                {question.label}
                {question.required && <span aria-hidden="true" className="text-red-600 dark:text-red-400"> *</span>}
              </span>
            ) : (
              <label htmlFor={inputId} id={`${inputId}-label`} className="mb-1 block text-sm font-medium text-slate-800 dark:text-slate-200">
                {question.label}
                {question.required && <span aria-hidden="true" className="text-red-600 dark:text-red-400"> *</span>}
              </label>
            )}
            {question.help_text && (
              <p id={`${inputId}-help`} className="mb-1 text-xs text-slate-500 dark:text-slate-400">
                {question.help_text}
              </p>
            )}
            <QuestionControl
              question={question}
              value={values[question.id]}
              onChange={(value) => onChange({ ...values, [question.id]: value })}
              disabled={disabled}
              inputId={inputId}
              describedBy={describedBy}
            />
            {error && (
              <p id={`${inputId}-error`} role="alert" className="mt-1 text-sm text-red-600 dark:text-red-400">
                {t(`errors.${error}`, { defaultValue: t('errors.unknown', { code: error }) })}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
