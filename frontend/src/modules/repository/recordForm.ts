/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// What a record's form holds and how it becomes the request body. Every value
// is edited as text: '' is "not set", a boolean is '' / 'true' / 'false', an
// image or a reference is the id of what it points at. A list or map is an
// array of entries (a list ignores `key`; the order is the array's). The
// backend validates everything again and answers with codes keyed by
// attribute id (or "<attribute id>.<index or key>" for one element).

import { elementTypeOf, listValues, mapEntries, newId, MAX_TEXT_LENGTH, type Attribute, type ElementType, type StoredValue } from './api'

export interface Entry {
  /** Only for React keys. */
  id: string
  key: string
  value: string
}

export type DraftValue = string | Entry[]
export type Drafts = Record<string, DraftValue>

/** A stored simple value as the text the form edits. */
export function simpleToDraft(value: StoredValue): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

export function initialDrafts(attributes: Attribute[], data: Record<string, StoredValue> = {}): Drafts {
  const drafts: Drafts = {}
  for (const attribute of attributes) {
    const stored = data[attribute.id]
    if (attribute.type === 'list') {
      drafts[attribute.id] = listValues(stored).map((value) => ({ id: newId(), key: '', value: simpleToDraft(value) }))
    } else if (attribute.type === 'map') {
      drafts[attribute.id] = mapEntries(stored).map(([key, value]) => ({ id: newId(), key, value: simpleToDraft(value) }))
    } else {
      drafts[attribute.id] = simpleToDraft(stored)
    }
  }
  return drafts
}

/** The value to send for one simple draft: undefined when it is not set, or an error code when it cannot be sent. */
export function simpleFromDraft(type: ElementType, draft: string): { value?: StoredValue; error?: string } {
  const text = draft.trim()
  if (text === '') return {}
  if (type === 'number') {
    const number = Number(text)
    return Number.isFinite(number) ? { value: number } : { error: 'invalid_number' }
  }
  if (type === 'boolean') return { value: text === 'true' }
  if (type === 'text' && text.length > MAX_TEXT_LENGTH) return { error: 'too_long' }
  return { value: text }
}

export interface BuiltData {
  data: Record<string, StoredValue>
  /** Problems found before sending: attribute id (or "<id>.<n>") -> code. */
  errors: Record<string, string>
}

export function buildData(attributes: Attribute[], drafts: Drafts): BuiltData {
  const data: Record<string, StoredValue> = {}
  const errors: Record<string, string> = {}
  for (const attribute of attributes) {
    const draft = drafts[attribute.id]
    const type = elementTypeOf(attribute)
    if (attribute.type === 'list' || attribute.type === 'map') {
      const entries = (draft as Entry[]) ?? []
      const elements: StoredValue[] = []
      const mapped: Record<string, StoredValue> = {}
      entries.forEach((entry, index) => {
        const built = simpleFromDraft(type, entry.value)
        const emptyEntry = built.value === undefined && !built.error && entry.key.trim() === ''
        if (emptyEntry) return
        if (built.error) errors[`${attribute.id}.${attribute.type === 'list' ? index : entry.key}`] = built.error
        else if (attribute.type === 'map') {
          if (entry.key.trim() === '') errors[`${attribute.id}.${entry.key}`] = 'invalid_key'
          else if (built.value === undefined) errors[`${attribute.id}.${entry.key}`] = 'required'
          else mapped[entry.key] = built.value
        } else if (built.value !== undefined) elements.push(built.value)
        else errors[`${attribute.id}.${index}`] = 'required'
      })
      const stored = attribute.type === 'list' ? elements : mapped
      const size = attribute.type === 'list' ? elements.length : Object.keys(mapped).length
      if (size > 0) data[attribute.id] = stored
      else if (attribute.required) errors[attribute.id] = 'required'
      continue
    }
    const built = simpleFromDraft(type, (draft as string) ?? '')
    if (built.error) errors[attribute.id] = built.error
    else if (built.value !== undefined) data[attribute.id] = built.value
    else if (attribute.required) errors[attribute.id] = 'required'
  }
  return { data, errors }
}
