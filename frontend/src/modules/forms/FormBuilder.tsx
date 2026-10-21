/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  OPERATORS_BY_TYPE,
  QUESTION_TYPES,
  fetchJson,
  newId,
  newOptionId,
  type Condition,
  type FormDefinition,
  type Operator,
  type Option,
  type Question,
  type QuestionConfig,
  type QuestionType,
} from './api'
import { inputClass, labelClass, primaryButtonClass, secondaryButtonClass, smallInputClass } from './ui'

const NO_VALUE: Operator[] = ['answered', 'not_answered']
const DATE_TYPES: QuestionType[] = ['date', 'time', 'datetime']

function isChoice(type: QuestionType): boolean {
  return type === 'checkbox' || type === 'radio'
}

function defaultConfig(type: QuestionType, previous?: QuestionConfig): QuestionConfig {
  const options = previous?.options?.length ? previous.options : [{ id: newOptionId(), label: '' }, { id: newOptionId(), label: '' }]
  switch (type) {
    case 'checkbox':
      return { options, min_select: 0, max_select: null }
    case 'radio':
      return { options }
    case 'text':
      return { multiline: false, min_length: 0, max_length: 2000, regex: null }
    case 'number':
      return { kind: 'integer', min: null, max: null }
    default:
      return { min: null, max: null }
  }
}

function newQuestion(type: QuestionType): Question {
  return { id: newId(), position: 0, type, label: '', help_text: '', required: false, config: defaultConfig(type), conditions: [] }
}

function numberOrNull(value: unknown): number | null {
  return value === '' || value === null || value === undefined ? null : Number(value)
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/** The configuration as the server wants it: only the keys of the question's type, blanks as null. */
function cleanConfig(question: Question): QuestionConfig {
  const { config, type } = question
  const options = (config.options ?? []).map((option) => ({ id: option.id, label: option.label.trim() }))
  switch (type) {
    case 'checkbox':
      return { options, min_select: Number(config.min_select ?? 0), max_select: numberOrNull(config.max_select) }
    case 'radio':
      return { options }
    case 'text':
      return {
        multiline: Boolean(config.multiline),
        min_length: Number(config.min_length ?? 0),
        max_length: Number(config.max_length ?? 2000),
        regex: stringOrNull(config.regex)?.trim() ?? null,
      }
    case 'number':
      return { kind: config.kind ?? 'integer', min: numberOrNull(config.min), max: numberOrNull(config.max) }
    default:
      return { min: stringOrNull(config.min), max: stringOrNull(config.max) }
  }
}

function toPayload(question: Question) {
  return {
    id: question.id,
    type: question.type,
    label: question.label.trim(),
    help_text: question.help_text.trim(),
    required: question.required,
    config: cleanConfig(question),
    conditions: question.conditions.map((c) => ({
      question_id: c.question_id,
      operator: c.operator,
      value: NO_VALUE.includes(c.operator) ? null : c.value,
    })),
  }
}

/** Why a condition is not (or no longer) valid, as a key under builder.problems, or null. */
function conditionProblem(questions: Question[], index: number, condition: Condition): string | null {
  const sourceIndex = questions.findIndex((q) => q.id === condition.question_id)
  if (sourceIndex < 0) return 'sourceMissing'
  if (sourceIndex >= index) return 'sourceNotEarlier'
  const source = questions[sourceIndex]
  if (!OPERATORS_BY_TYPE[source.type].includes(condition.operator)) return 'operatorMismatch'
  if (NO_VALUE.includes(condition.operator)) return null
  const value = condition.value
  if (condition.operator === 'contains' || condition.operator === 'not_contains' || source.type === 'radio') {
    return (source.config.options ?? []).some((option) => option.id === value) ? null : 'valueMissing'
  }
  if (source.type === 'number') return typeof value === 'number' && Number.isFinite(value) ? null : 'valueMissing'
  return typeof value === 'string' && value.trim() !== '' ? null : 'valueMissing'
}

/** Problems that would make the server refuse the form, found before asking it. */
function formProblems(questions: Question[]): { index: number; key: string }[] {
  const problems: { index: number; key: string }[] = []
  questions.forEach((question, index) => {
    if (question.label.trim() === '') problems.push({ index, key: 'labelMissing' })
    if (isChoice(question.type)) {
      const options = question.config.options ?? []
      if (options.length === 0 || options.some((option) => option.label.trim() === '')) problems.push({ index, key: 'optionLabelMissing' })
    }
    if (question.conditions.some((condition) => conditionProblem(questions, index, condition) !== null)) {
      problems.push({ index, key: 'conditionInvalid' })
    }
  })
  return problems
}

/** A server refusal (FastAPI's validation errors) as lines of text, each with the question it concerns. */
function describeServerError(detail: unknown, questionLabel: string): string[] {
  if (Array.isArray(detail)) {
    return detail.slice(0, 5).map((item: { loc?: unknown[]; msg?: string }) => {
      const at = item.loc?.indexOf('questions') ?? -1
      const index = at >= 0 ? item.loc?.[at + 1] : undefined
      const where = typeof index === 'number' ? `${questionLabel} ${index + 1}: ` : ''
      return `${where}${(item.msg ?? '').replace(/Value error, /g, '')}`
    })
  }
  return typeof detail === 'string' ? [detail] : []
}

// --- Editors of the parts of one question -----------------------------------------------------------------

function OptionsEditor({ options, onChange }: { options: Option[]; onChange: (options: Option[]) => void }) {
  const { t } = useTranslation('forms')
  return (
    <div className="space-y-2">
      <span className={labelClass}>{t('builder.options')}</span>
      {options.map((option, index) => (
        <div key={option.id} className="flex items-center gap-2">
          <input
            value={option.label}
            maxLength={200}
            aria-label={t('builder.optionLabel', { number: index + 1 })}
            placeholder={t('builder.optionLabel', { number: index + 1 })}
            onChange={(e) => onChange(options.map((o) => (o.id === option.id ? { ...o, label: e.target.value } : o)))}
            className={`${smallInputClass} flex-1`}
          />
          <button
            type="button"
            disabled={options.length <= 1}
            onClick={() => onChange(options.filter((o) => o.id !== option.id))}
            aria-label={t('builder.removeOption', { number: index + 1 })}
            className={secondaryButtonClass}
          >
            ✕
          </button>
        </div>
      ))}
      <button type="button" disabled={options.length >= 50} onClick={() => onChange([...options, { id: newOptionId(), label: '' }])} className={secondaryButtonClass}>
        {t('builder.addOption')}
      </button>
    </div>
  )
}

function ConfigEditor({ question, onChange }: { question: Question; onChange: (config: QuestionConfig) => void }) {
  const { t } = useTranslation('forms')
  const { config, type } = question
  const set = (patch: Partial<QuestionConfig>) => onChange({ ...config, ...patch })
  const intValue = (raw: string): number | undefined => (raw === '' ? undefined : Number(raw))

  return (
    <div className="space-y-3">
      {isChoice(type) && <OptionsEditor options={config.options ?? []} onChange={(options) => set({ options })} />}

      {type === 'checkbox' && (
        <div className="grid grid-cols-2 gap-3 sm:max-w-md">
          <label className="text-sm text-slate-600 dark:text-slate-400">
            {t('builder.minSelect')}
            <input type="number" min={0} value={config.min_select ?? 0} onChange={(e) => set({ min_select: intValue(e.target.value) })} className={`${smallInputClass} mt-1 w-full`} />
          </label>
          <label className="text-sm text-slate-600 dark:text-slate-400">
            {t('builder.maxSelect')}
            <input type="number" min={1} value={config.max_select ?? ''} placeholder={t('builder.noLimit')} onChange={(e) => set({ max_select: e.target.value === '' ? null : Number(e.target.value) })} className={`${smallInputClass} mt-1 w-full`} />
          </label>
        </div>
      )}

      {type === 'text' && (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={Boolean(config.multiline)} onChange={(e) => set({ multiline: e.target.checked })} />
            {t('builder.multiline')}
          </label>
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            <label className="text-sm text-slate-600 dark:text-slate-400">
              {t('builder.minLength')}
              <input type="number" min={0} max={2000} value={config.min_length ?? 0} onChange={(e) => set({ min_length: intValue(e.target.value) })} className={`${smallInputClass} mt-1 w-full`} />
            </label>
            <label className="text-sm text-slate-600 dark:text-slate-400">
              {t('builder.maxLength')}
              <input type="number" min={1} max={2000} value={config.max_length ?? 2000} onChange={(e) => set({ max_length: intValue(e.target.value) })} className={`${smallInputClass} mt-1 w-full`} />
            </label>
          </div>
          <label className="block text-sm text-slate-600 dark:text-slate-400">
            {t('builder.regex')}
            <input value={config.regex ?? ''} maxLength={200} spellCheck={false} onChange={(e) => set({ regex: e.target.value })} className={`${smallInputClass} mt-1 w-full font-mono`} />
            <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{t('builder.regexHint')}</span>
          </label>
        </div>
      )}

      {type === 'number' && (
        <div className="grid grid-cols-3 gap-3 sm:max-w-lg">
          <label className="text-sm text-slate-600 dark:text-slate-400">
            {t('builder.numberKind')}
            <select value={config.kind ?? 'integer'} onChange={(e) => set({ kind: e.target.value as 'integer' | 'decimal' })} className={`${smallInputClass} mt-1 w-full`}>
              <option value="integer">{t('builder.integer')}</option>
              <option value="decimal">{t('builder.decimal')}</option>
            </select>
          </label>
          <label className="text-sm text-slate-600 dark:text-slate-400">
            {t('builder.min')}
            <input type="number" step="any" value={config.min ?? ''} onChange={(e) => set({ min: e.target.value })} className={`${smallInputClass} mt-1 w-full`} />
          </label>
          <label className="text-sm text-slate-600 dark:text-slate-400">
            {t('builder.max')}
            <input type="number" step="any" value={config.max ?? ''} onChange={(e) => set({ max: e.target.value })} className={`${smallInputClass} mt-1 w-full`} />
          </label>
        </div>
      )}

      {DATE_TYPES.includes(type) && (
        <div className="grid grid-cols-2 gap-3 sm:max-w-lg">
          {(['min', 'max'] as const).map((bound) => (
            <label key={bound} className="text-sm text-slate-600 dark:text-slate-400">
              {t(bound === 'min' ? 'builder.notBefore' : 'builder.notAfter')}
              <input
                type={type === 'datetime' ? 'datetime-local' : type}
                value={typeof config[bound] === 'string' ? (config[bound] as string) : ''}
                onChange={(e) => set({ [bound]: e.target.value || null })}
                className={`${smallInputClass} mt-1 w-full`}
              />
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

function ConditionValue({ source, condition, onChange }: { source: Question; condition: Condition; onChange: (value: unknown) => void }) {
  const { t } = useTranslation('forms')
  if (NO_VALUE.includes(condition.operator)) return null
  if (condition.operator === 'contains' || condition.operator === 'not_contains' || source.type === 'radio') {
    return (
      <select value={typeof condition.value === 'string' ? condition.value : ''} onChange={(e) => onChange(e.target.value)} aria-label={t('builder.conditionValue')} className={smallInputClass}>
        <option value="">{t('builder.pickOption')}</option>
        {(source.config.options ?? []).map((option) => (
          <option key={option.id} value={option.id}>
            {option.label || t('builder.unnamedOption')}
          </option>
        ))}
      </select>
    )
  }
  if (source.type === 'number') {
    return <input type="number" step="any" value={typeof condition.value === 'number' ? condition.value : ''} aria-label={t('builder.conditionValue')} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} className={`${smallInputClass} w-28`} />
  }
  return (
    <input
      type={source.type === 'datetime' ? 'datetime-local' : source.type === 'text' ? 'text' : source.type}
      value={typeof condition.value === 'string' ? condition.value : ''}
      aria-label={t('builder.conditionValue')}
      onChange={(e) => onChange(e.target.value)}
      className={smallInputClass}
    />
  )
}

function ConditionsEditor({ questions, index, onChange }: { questions: Question[]; index: number; onChange: (conditions: Condition[]) => void }) {
  const { t } = useTranslation('forms')
  const question = questions[index]
  const earlier = questions.slice(0, index)
  if (earlier.length === 0) return null

  function add() {
    const source = earlier[earlier.length - 1]
    onChange([...question.conditions, { question_id: source.id, operator: OPERATORS_BY_TYPE[source.type][0], value: null }])
  }

  function change(ci: number, patch: Partial<Condition>) {
    onChange(question.conditions.map((c, i) => (i === ci ? { ...c, ...patch } : c)))
  }

  return (
    <div className="space-y-2 rounded-xl border border-dashed border-slate-300 p-3 dark:border-slate-700">
      <span className="block text-sm font-medium text-slate-700 dark:text-slate-300">{t('builder.showOnlyWhen')}</span>
      {question.conditions.length === 0 && <p className="text-xs text-slate-500 dark:text-slate-400">{t('builder.alwaysShown')}</p>}
      {question.conditions.map((condition, ci) => {
        const source = questions.find((q) => q.id === condition.question_id)
        const problem = conditionProblem(questions, index, condition)
        return (
          <div key={ci} className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={condition.question_id}
                aria-label={t('builder.conditionSource')}
                onChange={(e) => {
                  const next = questions.find((q) => q.id === e.target.value)
                  const operators = next ? OPERATORS_BY_TYPE[next.type] : []
                  change(ci, {
                    question_id: e.target.value,
                    operator: operators.includes(condition.operator) ? condition.operator : (operators[0] ?? condition.operator),
                    value: null,
                  })
                }}
                className={smallInputClass}
              >
                {!source && <option value={condition.question_id}>{t('builder.sourceMissing')}</option>}
                {earlier.map((q, qi) => (
                  <option key={q.id} value={q.id}>
                    {qi + 1}. {q.label || t('builder.untitled')}
                  </option>
                ))}
              </select>
              <select
                value={condition.operator}
                aria-label={t('builder.conditionOperator')}
                onChange={(e) => change(ci, { operator: e.target.value as Operator, value: null })}
                className={smallInputClass}
              >
                {(source ? OPERATORS_BY_TYPE[source.type] : [condition.operator]).map((operator) => (
                  <option key={operator} value={operator}>
                    {t(`operators.${operator}`)}
                  </option>
                ))}
              </select>
              {source && <ConditionValue source={source} condition={condition} onChange={(value) => change(ci, { value })} />}
              <button type="button" onClick={() => onChange(question.conditions.filter((_, i) => i !== ci))} aria-label={t('builder.removeCondition')} className={secondaryButtonClass}>
                ✕
              </button>
            </div>
            {problem && <p role="alert" className="text-xs text-red-600 dark:text-red-400">{t(`builder.problems.${problem}`)}</p>}
          </div>
        )
      })}
      <button type="button" disabled={question.conditions.length >= 10} onClick={add} className={secondaryButtonClass}>
        {t('builder.addCondition')}
      </button>
    </div>
  )
}

// --- The builder --------------------------------------------------------------------------------------------

/**
 * The administrators' editor of a form's questions (for modules that own a
 * form and embed it in their own admin page): add, order and delete
 * questions, set each one's type, wording, whether it is required and what its
 * type needs (options, limits, a pattern), and the conditions that show it only
 * for certain earlier answers. It loads the form itself and saves the whole
 * list at once (PUT .../questions); `onSaved` is called with what the server
 * stored. A condition that no longer holds (its source question was moved
 * below it, deleted, or changed type) is flagged and blocks saving until fixed.
 */
export default function FormBuilder({ formId, onSaved }: { formId: string; onSaved?: (questions: Question[]) => void }) {
  const { t } = useTranslation('forms')
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [newType, setNewType] = useState<QuestionType>('text')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [messages, setMessages] = useState<{ kind: 'ok' | 'error'; lines: string[] } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<FormDefinition>(`${API_BASE}/manage/${formId}`)
      .then((form) => {
        if (cancelled) return
        setQuestions(form.questions)
        setDirty(false)
      })
      .catch(() => !cancelled && setMessages({ kind: 'error', lines: [t('builder.loadError')] }))
    return () => {
      cancelled = true
    }
  }, [formId, t])

  if (questions === null) {
    return <p className="text-slate-500 dark:text-slate-400">{messages ? messages.lines[0] : t('common.loading')}</p>
  }

  const edit = (next: Question[]) => {
    setQuestions(next)
    setDirty(true)
    setMessages(null)
  }
  const patch = (index: number, change: Partial<Question>) => edit(questions.map((q, i) => (i === index ? { ...q, ...change } : q)))

  function changeType(index: number, type: QuestionType) {
    const current = questions![index]
    patch(index, { type, config: defaultConfig(type, isChoice(current.type) ? current.config : undefined) })
  }

  function move(index: number, delta: number) {
    const target = index + delta
    if (target < 0 || target >= questions!.length) return
    const next = [...questions!]
    ;[next[index], next[target]] = [next[target], next[index]]
    edit(next)
  }

  function remove(index: number) {
    const removed = questions![index].id
    edit(
      questions!
        .filter((_, i) => i !== index)
        .map((q) => ({ ...q, conditions: q.conditions.filter((c) => c.question_id !== removed) })),
    )
  }

  async function save() {
    const problems = formProblems(questions!)
    if (problems.length > 0) {
      setMessages({ kind: 'error', lines: problems.map((p) => `${t('builder.question')} ${p.index + 1}: ${t(`builder.problems.${p.key}`)}`) })
      return
    }
    setSaving(true)
    setMessages(null)
    try {
      const saved = await fetchJson<FormDefinition>(`${API_BASE}/manage/${formId}/questions`, {
        method: 'PUT',
        body: JSON.stringify({ questions: questions!.map(toPayload) }),
      })
      setQuestions(saved.questions)
      setDirty(false)
      setMessages({ kind: 'ok', lines: [t('builder.saved')] })
      onSaved?.(saved.questions)
    } catch (err) {
      const { status, detail } = err as { status?: number; detail?: unknown }
      const lines = status === 422 ? describeServerError(detail, t('builder.question')) : []
      setMessages({ kind: 'error', lines: lines.length > 0 ? lines : [t(status === 409 ? 'builder.conflict' : 'builder.saveError')] })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      {questions.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">{t('builder.empty')}</p>}

      <ol className="space-y-4">
        {questions.map((question, index) => (
          <li key={question.id} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">{t('builder.question')} {index + 1}</span>
              <div className="flex gap-1">
                <button type="button" disabled={index === 0} onClick={() => move(index, -1)} aria-label={t('builder.moveUp')} className={secondaryButtonClass}>↑</button>
                <button type="button" disabled={index === questions.length - 1} onClick={() => move(index, 1)} aria-label={t('builder.moveDown')} className={secondaryButtonClass}>↓</button>
                <button type="button" onClick={() => remove(index)} className="rounded-lg px-3 py-1.5 text-sm text-red-600 dark:text-red-400">{t('builder.delete')}</button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
              <div>
                <label htmlFor={`q-type-${question.id}`} className={labelClass}>{t('builder.type')}</label>
                <select id={`q-type-${question.id}`} value={question.type} onChange={(e) => changeType(index, e.target.value as QuestionType)} className={inputClass}>
                  {QUESTION_TYPES.map((type) => (
                    <option key={type} value={type}>{t(`types.${type}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={`q-label-${question.id}`} className={labelClass}>{t('builder.label')}</label>
                <input id={`q-label-${question.id}`} value={question.label} maxLength={300} onChange={(e) => patch(index, { label: e.target.value })} className={inputClass} />
              </div>
            </div>
            <div>
              <label htmlFor={`q-help-${question.id}`} className={labelClass}>{t('builder.helpText')}</label>
              <input id={`q-help-${question.id}`} value={question.help_text} maxLength={500} onChange={(e) => patch(index, { help_text: e.target.value })} className={inputClass} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={question.required} onChange={(e) => patch(index, { required: e.target.checked })} />
              {t('builder.required')}
            </label>

            <ConfigEditor question={question} onChange={(config) => patch(index, { config })} />
            <ConditionsEditor questions={questions} index={index} onChange={(conditions) => patch(index, { conditions })} />
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="forms-new-type" className="sr-only">{t('builder.type')}</label>
        <select id="forms-new-type" value={newType} onChange={(e) => setNewType(e.target.value as QuestionType)} className={smallInputClass}>
          {QUESTION_TYPES.map((type) => (
            <option key={type} value={type}>{t(`types.${type}`)}</option>
          ))}
        </select>
        <button type="button" disabled={questions.length >= 100} onClick={() => edit([...questions, newQuestion(newType)])} className={secondaryButtonClass}>
          {t('builder.addQuestion')}
        </button>
      </div>

      {messages && (
        <ul role={messages.kind === 'error' ? 'alert' : 'status'} className={`space-y-0.5 text-sm ${messages.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {messages.lines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-3">
        <button type="button" onClick={save} disabled={saving} className={primaryButtonClass}>
          {saving ? t('builder.saving') : t('builder.save')}
        </button>
        {dirty && <span className="text-xs text-amber-700 dark:text-amber-400">{t('builder.unsaved')}</span>}
      </div>
    </div>
  )
}
