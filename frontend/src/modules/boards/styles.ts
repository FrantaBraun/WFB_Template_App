/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The boards' look in one place, so the pages stay alike: violet is the
// action colour, gold / silver / bronze belong to the podium and nothing else.
// Full class names only - Tailwind finds classes by scanning the source for them.

/** A raised, rounded panel: a post, a category, a form. */
export const card = 'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/70'

export const primaryButton =
  'inline-flex items-center justify-center gap-1.5 rounded-full bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-violet-600 dark:hover:bg-violet-500'

export const secondaryButton =
  'inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 px-4 py-2 text-sm font-medium transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800'

/** A small label: a count, a state. */
export const chip =
  'inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300'

/** A chip in the action colour: "your post". */
export const accentChip =
  'inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-medium text-violet-800 dark:bg-violet-500/20 dark:text-violet-200'

/** How a post looks at one place in the ranking. */
export interface Tier {
  /** The medal for the podium, null below it. */
  medal: string | null
  /** The whole look of the card - border, background, shadow - so nothing conflicts with the plain card's. */
  card: string
  /** The colour of the score. */
  score: string
  /** The size of the title. */
  title: string
}

const FIRST: Tier = {
  medal: '🥇',
  card: 'rounded-2xl border border-amber-300 bg-gradient-to-br from-amber-50 via-white to-white shadow-md ring-1 ring-amber-200/70 dark:border-amber-400/40 dark:from-amber-400/10 dark:via-slate-900/70 dark:to-slate-900/70 dark:ring-amber-400/20',
  score: 'text-amber-600 dark:text-amber-300',
  title: 'text-xl',
}

const SECOND: Tier = {
  medal: '🥈',
  card: 'rounded-2xl border border-slate-300 bg-gradient-to-br from-slate-100 via-white to-white shadow ring-1 ring-slate-200 dark:border-slate-400/40 dark:from-slate-400/10 dark:via-slate-900/70 dark:to-slate-900/70 dark:ring-slate-400/20',
  score: 'text-slate-600 dark:text-slate-200',
  title: 'text-lg',
}

const THIRD: Tier = {
  medal: '🥉',
  card: 'rounded-2xl border border-orange-300 bg-gradient-to-br from-orange-50 via-white to-white shadow ring-1 ring-orange-200/70 dark:border-orange-400/40 dark:from-orange-400/10 dark:via-slate-900/70 dark:to-slate-900/70 dark:ring-orange-400/20',
  score: 'text-orange-600 dark:text-orange-300',
  title: 'text-lg',
}

const REST: Tier = { medal: null, card, score: 'text-slate-800 dark:text-slate-100', title: 'text-lg' }

/** The podium is the first three places; everybody else gets the plain card. */
export function tierOf(rank: number): Tier {
  return rank === 1 ? FIRST : rank === 2 ? SECOND : rank === 3 ? THIRD : REST
}
