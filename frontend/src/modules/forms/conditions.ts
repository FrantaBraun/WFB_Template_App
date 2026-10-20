/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Which questions of a form are shown for the answers given so far - a LITERAL
// translation of backend/app/modules/forms/logic.py (condition_holds,
// visible_questions); read its docstring for the semantics. The server
// decides what is accepted; this only decides what the visitor is shown, so the
// two must never disagree. What keeps them honest is the shared vectors in
// backend/tests/data/forms_visibility_vectors.json: the backend suite checks
// logic.py against them, and this file is checked against the same file by
// hand (the frontend has no test runner and none is to be added without
// asking) - see "Forms" in CLAUDE.md for the one-line node command. Change one
// side, change the other, and add a vector.
//
// Plain TypeScript with no imports and nothing but erasable type syntax, so
// that node can run it directly.

export type Operator =
  | 'answered'
  | 'not_answered'
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'not_contains'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'

export type QuestionType = 'checkbox' | 'radio' | 'text' | 'number' | 'date' | 'time' | 'datetime'

export interface Condition {
  question_id: string
  operator: Operator
  value?: unknown
}

export interface ConditionQuestion {
  id: string
  type: string
  conditions?: Condition[]
}

const ALWAYS: Operator[] = ['answered', 'not_answered']

/** Which operators a condition on a question of each type may use (mirrors OPERATORS_BY_TYPE). */
export const OPERATORS_BY_TYPE: Record<QuestionType, Operator[]> = {
  checkbox: [...ALWAYS, 'contains', 'not_contains'],
  radio: [...ALWAYS, 'equals', 'not_equals'],
  text: [...ALWAYS, 'equals', 'not_equals'],
  number: [...ALWAYS, 'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'],
  date: [...ALWAYS, 'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'],
  time: [...ALWAYS, 'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'],
  datetime: [...ALWAYS, 'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'],
}

const DATE_TYPES = ['date', 'time', 'datetime']

/** None, an empty / blank string and an empty list are "no answer"; 0 is an answer. */
export function isAnswered(value: unknown): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.length > 0
  return true
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function isEqual(sourceType: string, value: unknown, expected: unknown): boolean {
  if (sourceType === 'number') {
    const a = asNumber(value)
    const b = asNumber(expected)
    return a !== null && b !== null && a === b
  }
  return typeof value === 'string' && typeof expected === 'string' && value.trim() === expected.trim()
}

function isOrdered(operator: string, sourceType: string, value: unknown, expected: unknown): boolean {
  let a: number | string | null
  let b: number | string | null
  if (sourceType === 'number') {
    a = asNumber(value)
    b = asNumber(expected)
  } else if (DATE_TYPES.includes(sourceType) && typeof value === 'string' && typeof expected === 'string') {
    // Fixed-width ISO forms: string order is time order.
    a = value
    b = expected
  } else {
    return false
  }
  if (a === null || b === null) return false
  if (operator === 'gt') return a > b
  if (operator === 'gte') return a >= b
  if (operator === 'lt') return a < b
  return a <= b
}

/** Does one condition hold, given the (typed) answer to its source question? */
export function conditionHolds(condition: Condition, sourceType: string, value: unknown): boolean {
  const { operator } = condition
  const expected = condition.value
  const answered = isAnswered(value)
  if (operator === 'answered') return answered
  if (operator === 'not_answered') return !answered
  if (operator === 'contains') return answered && Array.isArray(value) && value.includes(expected)
  if (operator === 'not_contains') return !(answered && Array.isArray(value) && value.includes(expected))
  if (operator === 'equals') return answered && isEqual(sourceType, value, expected)
  if (operator === 'not_equals') return !(answered && isEqual(sourceType, value, expected))
  if (operator === 'gt' || operator === 'gte' || operator === 'lt' || operator === 'lte') {
    return answered && isOrdered(operator, sourceType, value, expected)
  }
  return false
}

/**
 * The questions shown for these (typed) answers, in order. One pass is enough
 * because a condition only refers to an earlier question; a hidden question's
 * answer is ignored, so hiding chains.
 */
export function visibleQuestions<T extends ConditionQuestion>(questions: T[], answers: Record<string, unknown>): T[] {
  const byId = new Map(questions.map((question) => [question.id, question]))
  const effective: Record<string, unknown> = {}
  const shown: T[] = []
  for (const question of questions) {
    const holds = (question.conditions ?? []).every((condition) => {
      const source = byId.get(condition.question_id)
      return conditionHolds(condition, source ? source.type : 'text', effective[condition.question_id])
    })
    if (holds) {
      shown.push(question)
      if (question.id in answers) effective[question.id] = answers[question.id]
    }
  }
  return shown
}
