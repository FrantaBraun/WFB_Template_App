/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import {
  ATTRIBUTE_TYPES,
  ELEMENT_TYPES,
  newId,
  type Attribute,
  type AttributeType,
  type ElementType,
  type TableSummary,
} from './api'
import { cardClass, errorTextClass, hintClass, inputClass, labelClass, secondaryButtonClass } from './ui'

/** An attribute as the editor holds it. `saved` ones exist on the server: their type and what they point at are locked. */
export interface AttributeDraft {
  id: string
  name: string
  description: string
  type: AttributeType
  required: boolean
  show_in_list: boolean
  elementType: ElementType
  targetTableId: string
  saved: boolean
}

export function emptyDraft(): AttributeDraft {
  return {
    id: newId(),
    name: '',
    description: '',
    type: 'text',
    required: false,
    show_in_list: false,
    elementType: 'text',
    targetTableId: '',
    saved: false,
  }
}

export function draftFromAttribute(attribute: Attribute): AttributeDraft {
  return {
    id: attribute.id,
    name: attribute.name,
    description: attribute.description,
    type: attribute.type,
    required: attribute.required,
    show_in_list: attribute.show_in_list,
    elementType: attribute.config.element_type ?? 'text',
    targetTableId: attribute.config.table_id ?? '',
    saved: true,
  }
}

/** Whether the attribute points at another table (a reference, or a list/map of references). */
export function pointsAtTable(draft: Pick<AttributeDraft, 'type' | 'elementType'>): boolean {
  return draft.type === 'reference' || ((draft.type === 'list' || draft.type === 'map') && draft.elementType === 'reference')
}

/** The body of PUT .../attributes for these drafts. */
export function draftsToRequest(drafts: AttributeDraft[]) {
  return drafts.map((draft) => {
    const config: Record<string, string> = {}
    if (draft.type === 'list' || draft.type === 'map') config.element_type = draft.elementType
    if (pointsAtTable(draft)) config.table_id = draft.targetTableId
    return {
      id: draft.id,
      name: draft.name.trim(),
      description: draft.description.trim(),
      type: draft.type,
      required: draft.type === 'boolean' ? false : draft.required,
      show_in_list: draft.show_in_list,
      config,
    }
  })
}

/** What is wrong with the drafts before they are sent: attribute id -> a translation key under `attributes.problems`. */
export function draftProblems(drafts: AttributeDraft[]): Record<string, string> {
  const problems: Record<string, string> = {}
  const seen = new Map<string, string>()
  for (const draft of drafts) {
    const name = draft.name.trim().toLowerCase()
    if (name === '') problems[draft.id] = 'nameRequired'
    else if (seen.has(name)) problems[draft.id] = 'nameTaken'
    else seen.set(name, draft.id)
    if (!problems[draft.id] && pointsAtTable(draft) && draft.targetTableId === '') problems[draft.id] = 'tableRequired'
  }
  return problems
}

interface Props {
  drafts: AttributeDraft[]
  onChange: (drafts: AttributeDraft[]) => void
  /** The tables of the repository a reference may point at. */
  tables: TableSummary[]
  /** The id of the table being edited (it may refer to itself); unset while it is being created, when it is not among `tables` yet. */
  selfTableId?: string
  /** Problems found on the client (draftProblems) and the server's codes, by attribute id. */
  problems: Record<string, string>
  serverErrors: Record<string, string>
  maxAttributes: number
}

function TargetSelect({
  id,
  value,
  onChange,
  tables,
  selfTableId,
  disabled,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  tables: TableSummary[]
  selfTableId?: string
  disabled: boolean
}) {
  const { t } = useTranslation('repository')
  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        {t('attributes.fields.targetTable')}
      </label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} className={inputClass}>
        <option value="">{t('attributes.chooseTable')}</option>
        {tables.map((table) => (
          <option key={table.id} value={table.id}>
            {table.name}
            {table.id === selfTableId ? ` ${t('attributes.thisTable')}` : ''}
          </option>
        ))}
      </select>
    </div>
  )
}

/**
 * The attributes of a table as a dynamic form: add, remove, reorder, and for
 * each its name, description, type (a list or map also its element type, a
 * reference the table it points at), whether it is required and whether it
 * is shown on the content page. A saved attribute's type and target are locked
 * - the server never lets them change; to change one, remove it and add it again.
 */
export default function AttributeEditor({ drafts, onChange, tables, selfTableId, problems, serverErrors, maxAttributes }: Props) {
  const { t } = useTranslation('repository')

  function update(index: number, changes: Partial<AttributeDraft>) {
    onChange(drafts.map((draft, i) => (i === index ? { ...draft, ...changes } : draft)))
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= drafts.length) return
    const next = [...drafts]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <fieldset className="space-y-3">
      <legend className="mb-1 text-lg font-semibold">{t('attributes.title')}</legend>
      <p className={hintClass}>{t('attributes.systemNote')}</p>

      {drafts.length === 0 && <p className="rounded-xl border border-dashed repo-border p-4 text-sm text-slate-600 dark:text-slate-400">{t('attributes.empty')}</p>}

      <ol className="space-y-3">
        {drafts.map((draft, index) => {
          const base = `attribute-${draft.id}`
          const problem = problems[draft.id]
          const serverCode = serverErrors[draft.id]
          return (
            <li key={draft.id} className={`${cardClass} space-y-3 p-4`}>
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <label htmlFor={`${base}-name`} className={labelClass}>
                    {t('attributes.fields.name')}
                  </label>
                  <input
                    id={`${base}-name`}
                    value={draft.name}
                    onChange={(e) => update(index, { name: e.target.value })}
                    maxLength={120}
                    className={inputClass}
                    aria-invalid={problem !== undefined}
                  />
                </div>
                <div className="flex shrink-0 gap-1 pt-6">
                  <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={t('attributes.moveUp', { name: draft.name })} className={secondaryButtonClass}>
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, 1)}
                    disabled={index === drafts.length - 1}
                    aria-label={t('attributes.moveDown', { name: draft.name })}
                    className={secondaryButtonClass}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    onClick={() => onChange(drafts.filter((_, i) => i !== index))}
                    aria-label={t('attributes.remove', { name: draft.name })}
                    className="inline-flex items-center rounded-lg border border-red-300 px-2.5 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor={`${base}-type`} className={labelClass}>
                    {t('attributes.fields.type')}
                  </label>
                  <select
                    id={`${base}-type`}
                    value={draft.type}
                    disabled={draft.saved}
                    onChange={(e) => update(index, { type: e.target.value as AttributeType, required: e.target.value === 'boolean' ? false : draft.required })}
                    className={inputClass}
                  >
                    {ATTRIBUTE_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {t(`attributes.types.${type}`)}
                      </option>
                    ))}
                  </select>
                  {draft.saved && <p className={hintClass}>{t('attributes.typeLocked')}</p>}
                </div>

                {(draft.type === 'list' || draft.type === 'map') && (
                  <div>
                    <label htmlFor={`${base}-element`} className={labelClass}>
                      {t(draft.type === 'list' ? 'attributes.fields.listOf' : 'attributes.fields.mapOf')}
                    </label>
                    <select
                      id={`${base}-element`}
                      value={draft.elementType}
                      disabled={draft.saved}
                      onChange={(e) => update(index, { elementType: e.target.value as ElementType })}
                      className={inputClass}
                    >
                      {ELEMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {t(`attributes.types.${type}`)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {pointsAtTable(draft) && (
                  <TargetSelect
                    id={`${base}-target`}
                    value={draft.targetTableId}
                    onChange={(value) => update(index, { targetTableId: value })}
                    tables={tables}
                    selfTableId={selfTableId}
                    disabled={draft.saved}
                  />
                )}
              </div>

              <div>
                <label htmlFor={`${base}-description`} className={labelClass}>
                  {t('attributes.fields.description')}
                </label>
                <input id={`${base}-description`} value={draft.description} onChange={(e) => update(index, { description: e.target.value })} maxLength={500} className={inputClass} />
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-700 dark:text-slate-300">
                {draft.type !== 'boolean' && (
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="repo-check" checked={draft.required} onChange={(e) => update(index, { required: e.target.checked })} />
                    {t('attributes.fields.required')}
                  </label>
                )}
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="repo-check" checked={draft.show_in_list} onChange={(e) => update(index, { show_in_list: e.target.checked })} />
                  {t('attributes.fields.showInList')}
                </label>
              </div>

              {problem && <p className={errorTextClass}>{t(`attributes.problems.${problem}`)}</p>}
              {serverCode && <p className={errorTextClass}>{t(`attributes.serverErrors.${serverCode}`, { defaultValue: t('attributes.serverErrors.generic') })}</p>}
            </li>
          )
        })}
      </ol>

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => onChange([...drafts, emptyDraft()])} disabled={drafts.length >= maxAttributes} className={secondaryButtonClass}>
          {t('attributes.add')}
        </button>
        <span className={hintClass}>{t('attributes.count', { count: drafts.length, max: maxAttributes })}</span>
      </div>
    </fieldset>
  )
}
