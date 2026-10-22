/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// What a table can be filtered and sorted by, and what the filter rows of the
// content page hold. Mirrors the backend's filters.py (OPERATORS, which fields
// there are): the server validates every definition and answers 422 for one it
// does not accept, so a mismatch here shows as an error, never as wrong data.

import { newId, type Attribute, type RefInfo } from './api'

export type FieldKind = 'text' | 'number' | 'boolean' | 'date' | 'datetime' | 'reference' | 'timestamp'

export const OPERATORS: Record<FieldKind, readonly string[]> = {
  text: ['contains', 'equals', 'empty', 'not_empty'],
  number: ['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'between', 'empty', 'not_empty'],
  boolean: ['equals', 'empty', 'not_empty'],
  date: ['eq', 'before', 'after', 'between', 'empty', 'not_empty'],
  datetime: ['eq', 'before', 'after', 'between', 'empty', 'not_empty'],
  reference: ['equals', 'empty', 'not_empty'],
  timestamp: ['eq', 'before', 'after', 'between'],
}

const NO_VALUE = new Set(['empty', 'not_empty'])
const FILTERABLE_TYPES = new Set(['text', 'number', 'boolean', 'date', 'datetime', 'reference'])

export interface FieldInfo {
  /** `name`, `slug`, `created_on` or an attribute id. */
  key: string
  /** The attribute's own name; undefined for the system fields (the caller translates those). */
  label?: string
  kind: FieldKind
  /** For a reference: the table it points at. */
  tableId?: string
}

/** The fields a table can be filtered and sorted by: the system ones, then its attributes of a simple type. */
export function fieldsFor(attributes: Attribute[]): FieldInfo[] {
  return [
    { key: 'name', kind: 'text' },
    { key: 'slug', kind: 'text' },
    { key: 'created_on', kind: 'timestamp' },
    ...attributes
      .filter((attribute) => FILTERABLE_TYPES.has(attribute.type))
      .map((attribute) => ({ key: attribute.id, label: attribute.name, kind: attribute.type as FieldKind, tableId: attribute.config.table_id })),
  ]
}

/** One filter row as the page holds it. Values are text, as typed; a reference also keeps what is known about its record. */
export interface ConditionDraft {
  id: string
  field: string
  op: string
  value: string
  value2: string
  refInfo?: RefInfo
}

export function newCondition(field: FieldInfo): ConditionDraft {
  return { id: newId(), field: field.key, op: OPERATORS[field.kind][0], value: '', value2: '' }
}

export function operatorNeedsValue(op: string): boolean {
  return !NO_VALUE.has(op)
}

export function operatorNeedsTwoValues(op: string): boolean {
  return op === 'between'
}

function convert(kind: FieldKind, text: string): string | number | boolean | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  if (kind === 'number') {
    const number = Number(trimmed)
    return Number.isFinite(number) ? number : null
  }
  if (kind === 'boolean') return trimmed === 'true'
  return trimmed
}

export interface ConditionRequest {
  field: string
  op: string
  value?: string | number | boolean
  value2?: string | number | boolean
}

/** The condition to send, or null while the row is not complete (an empty value, say) - such a row is simply not applied yet. */
export function conditionToRequest(draft: ConditionDraft, field: FieldInfo | undefined): ConditionRequest | null {
  if (!field || !OPERATORS[field.kind].includes(draft.op)) return null
  if (!operatorNeedsValue(draft.op)) return { field: draft.field, op: draft.op }
  const value = convert(field.kind, draft.value)
  if (value === null) return null
  if (!operatorNeedsTwoValues(draft.op)) return { field: draft.field, op: draft.op, value }
  const value2 = convert(field.kind, draft.value2)
  return value2 === null ? null : { field: draft.field, op: draft.op, value, value2 }
}

export interface Sort {
  field: string
  dir: 'asc' | 'desc'
}

/** The sort after a click on a column header: ascending, then descending, then back to the default. */
export function nextSort(current: Sort | null, field: string): Sort | null {
  if (current?.field !== field) return { field, dir: 'asc' }
  return current.dir === 'asc' ? { field, dir: 'desc' } : null
}
