/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Small building blocks shared by the freelancer site's pages, so the look is
// decided in one place. Violet is the action colour (the same as the footer's
// WithFBraun link); everything else is the slate neutrals of the rest of the
// app, with dark: variants because dark mode is class-based.
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const focus = 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 dark:focus-visible:outline-violet-400'

export const primaryButton = `inline-flex items-center justify-center rounded-lg bg-violet-700 px-5 py-2.5 font-medium text-white transition-colors hover:bg-violet-800 dark:bg-violet-600 dark:hover:bg-violet-500 ${focus}`
export const secondaryButton = `inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-900 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 ${focus}`
export const card = 'rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900'
export const mutedText = 'text-slate-600 dark:text-slate-400'
export const textLink = `font-medium text-violet-700 underline decoration-violet-300 underline-offset-4 hover:decoration-violet-700 dark:text-violet-400 dark:decoration-violet-700 dark:hover:decoration-violet-400 ${focus}`

/** Width and gutters every page of the site shares (the header is max-w-4xl too). */
export const container = 'mx-auto w-full max-w-4xl px-6'

export function ButtonLink({ to, variant = 'primary', children }: { to: string; variant?: 'primary' | 'secondary'; children: ReactNode }) {
  return (
    <Link to={to} className={variant === 'primary' ? primaryButton : secondaryButton}>
      {children}
    </Link>
  )
}

/** A plain heading + optional lead paragraph on top of an inner page. */
export function PageShell({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <div className={`${container} py-12 text-slate-900 dark:text-slate-100 sm:py-16`}>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
      {lead && <p className={`mt-4 max-w-2xl text-lg ${mutedText}`}>{lead}</p>}
      <div className="mt-10 space-y-14">{children}</div>
    </div>
  )
}

export function Section({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      {intro && <p className={`mt-3 max-w-2xl ${mutedText}`}>{intro}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}

/** A call to action closing a page: a heading, one sentence and the contact button. */
export function ContactCta({ title, text, button }: { title: string; text: string; button: string }) {
  return (
    <section className="rounded-2xl bg-violet-50 p-8 text-center dark:bg-violet-950/40">
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      <p className={`mx-auto mt-3 max-w-xl ${mutedText}`}>{text}</p>
      <div className="mt-6">
        <ButtonLink to="/contact">{button}</ButtonLink>
      </div>
    </section>
  )
}

/** Paragraphs from a text where a blank line separates them (as in the contact and portfolio texts). */
export function Paragraphs({ text, className = '' }: { text: string; className?: string }) {
  return (
    <>
      {text
        .split(/\n\s*\n/)
        .map((p) => p.trim())
        .filter(Boolean)
        .map((paragraph, i) => (
          <p key={i} className={`whitespace-pre-line ${className}`}>
            {paragraph}
          </p>
        ))}
    </>
  )
}
