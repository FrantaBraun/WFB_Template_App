/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { HopIcon, Ornament, PubLogo } from '../components/PubGraphics'
import { PUB } from '../config/pub'
import usePageMeta from '../hooks/usePageMeta'
import { TodayMenu } from '../modules/pub_menu'
import { OpeningHours } from '../modules/table_reservations'

const primaryLink =
  'rounded-lg bg-hop px-6 py-3 text-base font-medium text-white shadow-sm hover:bg-hop/90 dark:bg-hop-dark dark:text-slate-950 dark:hover:bg-hop-dark/90'
const secondaryLink =
  'rounded-lg border border-slate-300 bg-white px-6 py-3 text-base font-medium text-slate-800 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800'

/**
 * The pub's front page: the name and what it is known for, the lunch menu of the
 * day and the opening hours (both from their modules), three reasons to come, and
 * a way to reserve. The (made-up) facts are in config/pub.ts, the words in the
 * locale files.
 */
export default function HomePage() {
  const { t } = useTranslation()
  usePageMeta()

  return (
    <div className="text-slate-900 dark:text-slate-100">
      <section className="pub-texture border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto max-w-4xl px-4 py-14 text-center sm:px-6 sm:py-24">
          <PubLogo className="mx-auto mb-5 h-16 w-16" />
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.3em] text-hop sm:text-sm dark:text-hop-dark">{t('home.eyebrow', { year: PUB.founded })}</p>
          <h1 className="font-display text-4xl leading-tight sm:text-6xl">{PUB.name}</h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600 dark:text-slate-300">{t('home.tagline')}</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/reservations" className={primaryLink}>{t('home.reserve')}</Link>
            <Link to="/menu" className={secondaryLink}>{t('home.menu')}</Link>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-4xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div>
          <h2 className="mb-4 text-2xl font-semibold">{t('home.todayTitle')}</h2>
          <TodayMenu />
        </div>
        <aside className="h-fit space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-2xl font-semibold">{t('home.hoursTitle')}</h2>
          <OpeningHours />
          <address className="space-y-1 border-t border-slate-200 pt-4 text-sm not-italic dark:border-slate-800">
            <p className="font-medium">{PUB.name}</p>
            <p>{PUB.street}</p>
            <p>{PUB.city}</p>
            <p>
              <a href={PUB.phoneHref} className="underline">{PUB.phone}</a>
            </p>
            <p>
              <a href={`mailto:${PUB.email}`} className="underline">{PUB.email}</a>
            </p>
          </address>
        </aside>
      </section>

      <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
        <Ornament className="mb-10" />
        <h2 className="mb-6 text-center text-2xl font-semibold sm:text-3xl">{t('home.highlightsTitle')}</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {(['kitchen', 'beer', 'party'] as const).map((key) => (
            <article key={key} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <HopIcon className="mb-3 h-8 w-8 text-hop dark:text-hop-dark" />
              <h3 className="mb-2 text-lg font-semibold">{t(`home.highlights.${key}.title`)}</h3>
              <p className="text-sm text-slate-600 dark:text-slate-300">{t(`home.highlights.${key}.text`)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="pub-texture border-t border-slate-200 dark:border-slate-800">
        <div className="mx-auto max-w-4xl px-4 py-12 text-center sm:px-6">
          <h2 className="text-2xl font-semibold sm:text-3xl">{t('home.ctaTitle')}</h2>
          <p className="mx-auto mt-3 max-w-xl text-slate-600 dark:text-slate-300">{t('home.ctaText')}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to="/reservations" className={primaryLink}>{t('home.reserve')}</Link>
            <Link to="/o-nas" className={secondaryLink}>{t('home.about')}</Link>
          </div>
        </div>
      </section>
    </div>
  )
}
