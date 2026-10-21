/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Ornament } from '../components/PubGraphics'
import { PUB } from '../config/pub'
import usePageMeta from '../hooks/usePageMeta'

const SECTIONS = ['story', 'kitchen', 'beer'] as const

/**
 * /o-nas - about the (made-up) pub: its story, its kitchen and beer, how to get
 * there, the operator's details and a plain notice that none of it is real. The
 * facts are in config/pub.ts, the words in the locale files (`about.*`).
 */
export default function About() {
  const { t } = useTranslation()
  usePageMeta({ title: t('about.title'), description: t('about.description') })

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 text-slate-900 sm:px-6 sm:py-14 dark:text-slate-100">
      <h1 className="font-display mb-3 text-3xl sm:text-5xl">{t('about.title')}</h1>
      <p className="mb-10 text-lg text-slate-600 dark:text-slate-300">{t('about.lead', { year: PUB.founded })}</p>

      <div className="space-y-10">
        {SECTIONS.map((key) => (
          <section key={key}>
            <h2 className="mb-3 text-2xl font-semibold">{t(`about.${key}.title`)}</h2>
            <div className="space-y-3 text-slate-700 dark:text-slate-300">
              {(t(`about.${key}.text`) as string).split('\n\n').map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
          </section>
        ))}
      </div>

      <Ornament className="my-10" />

      <div className="grid gap-6 sm:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 text-xl font-semibold">{t('about.contactTitle')}</h2>
          <address className="space-y-1 text-sm not-italic">
            <p className="font-medium">{PUB.name}</p>
            <p>{PUB.street}</p>
            <p>{PUB.city}</p>
            <p className="pt-2">
              {t('about.phone')}: <a href={PUB.phoneHref} className="underline">{PUB.phone}</a>
            </p>
            <p>
              {t('about.email')}: <a href={`mailto:${PUB.email}`} className="underline">{PUB.email}</a>
            </p>
          </address>
          <p className="mt-4 text-sm">
            <Link to="/reservations" className="underline">{t('about.reserveLink')}</Link>
          </p>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 text-xl font-semibold">{t('about.operatorTitle')}</h2>
          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="text-slate-500 dark:text-slate-400">{t('about.operator')}:</dt>
              <dd>{PUB.operator}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-slate-500 dark:text-slate-400">{t('about.ico')}:</dt>
              <dd>{PUB.ico}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-slate-500 dark:text-slate-400">{t('about.seat')}:</dt>
              <dd>{PUB.street}, {PUB.city}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-2xl font-semibold">{t('about.directionsTitle')}</h2>
        <p className="text-slate-700 dark:text-slate-300">{t('about.directions')}</p>
      </section>

      <p role="note" className="mt-10 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600 dark:border-slate-600 dark:text-slate-300">
        {t('about.demoNotice')}
      </p>
    </div>
  )
}
