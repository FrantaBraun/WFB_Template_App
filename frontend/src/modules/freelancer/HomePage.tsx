/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { usePublicData, type ContactInfo, type ProjectPreview } from './data'
import { JsonLd } from './seo'
import { ButtonLink, card, container, ContactCta, mutedText, Paragraphs, textLink } from './ui'

interface TextItem {
  title: string
  text: string
}

/** The landing page: who the site is for, what is offered, how the work goes, and a few projects. */
export default function HomePage() {
  const { t } = useTranslation('freelancer')
  usePageMeta({ title: t('home.metaTitle') })

  const projects = usePublicData<ProjectPreview[]>('/api/modules/portfolio/items?limit=3')
  const contact = usePublicData<ContactInfo>('/api/modules/kontaktni_formular/info')

  const services = t('home.services.items', { returnObjects: true }) as TextItem[]
  const principles = t('home.principles.items', { returnObjects: true }) as TextItem[]
  const instantParagraphs = t('home.instant.paragraphs', { returnObjects: true }) as string[]
  const aiParagraphs = t('home.ai.paragraphs', { returnObjects: true }) as string[]

  const sameAs = [contact?.details.github_url, contact?.details.linkedin_url].filter(Boolean)

  return (
    <div className="text-slate-900 dark:text-slate-100">
      <JsonLd
        id="person"
        data={{
          '@context': 'https://schema.org',
          '@type': 'Person',
          name: t('seo.personName'),
          jobTitle: t('seo.jobTitle'),
          url: window.location.origin,
          description: t('home.lead'),
          knowsAbout: services.map((service) => service.title),
          ...(sameAs.length > 0 ? { sameAs } : {}),
        }}
      />

      <section className="border-b border-slate-200 bg-gradient-to-b from-violet-50 to-white dark:border-slate-800 dark:from-violet-950/30 dark:to-slate-950">
        <div className={`${container} py-16 sm:py-24`}>
          <p className="inline-block rounded-full border border-violet-200 bg-white px-3 py-1 text-sm font-medium text-violet-800 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-200">
            {t('home.eyebrow')}
          </p>
          <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">{t('home.title')}</h1>
          <p className={`mt-6 max-w-2xl text-lg ${mutedText}`}>{t('home.lead')}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink to="/contact">{t('common.contactMe')}</ButtonLink>
            <ButtonLink to="/portfolio" variant="secondary">
              {t('home.portfolioButton')}
            </ButtonLink>
          </div>
        </div>
      </section>

      <div className={`${container} space-y-20 py-16`}>
        <section>
          <h2 className="text-2xl font-semibold tracking-tight">{t('home.services.title')}</h2>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2">
            {services.map((service) => (
              <li key={service.title} className={card}>
                <h3 className="text-lg font-semibold">{service.title}</h3>
                <p className={`mt-2 ${mutedText}`}>{service.text}</p>
              </li>
            ))}
          </ul>
          <p className="mt-5">
            <Link to="/services" className={textLink}>
              {t('home.services.all')} →
            </Link>
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold tracking-tight">{t('home.principles.title')}</h2>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2">
            {principles.map((principle) => (
              <li key={principle.title} className={`${card} border-l-4 border-l-violet-300 dark:border-l-violet-700`}>
                <h3 className="text-lg font-semibold">{principle.title}</h3>
                <p className={`mt-2 ${mutedText}`}>{principle.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className={`${card} sm:p-8`}>
          <h2 className="text-2xl font-semibold tracking-tight">{t('home.instant.title')}</h2>
          <div className={`mt-4 max-w-2xl space-y-3 ${mutedText}`}>
            {instantParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>

        <section className={`${card} sm:p-8`}>
          <h2 className="text-2xl font-semibold tracking-tight">{t('home.ai.title')}</h2>
          <div className={`mt-4 max-w-2xl space-y-3 ${mutedText}`}>
            {aiParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
          <p className="mt-5">
            <Link to="/about" className={textLink}>
              {t('home.ai.more')} →
            </Link>
          </p>
        </section>

        {projects && projects.length > 0 && (
          <section>
            <h2 className="text-2xl font-semibold tracking-tight">{t('home.portfolio.title')}</h2>
            <p className={`${card} mt-4 max-w-2xl py-4 ${mutedText}`}>{t('home.portfolio.intro')}</p>
            <ul className="mt-6 grid gap-4 sm:grid-cols-3">
              {projects.map((project) => (
                <li key={project.slug}>
                  <Link
                    to={`/portfolio/${project.slug}`}
                    className={`${card} block h-full transition-colors hover:border-violet-300 dark:hover:border-violet-700`}
                  >
                    <h3 className="font-semibold">{project.title}</h3>
                    <Paragraphs text={project.summary} className={`mt-2 text-sm ${mutedText}`} />
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-5">
              <Link to="/portfolio" className={textLink}>
                {t('home.portfolio.all')} →
              </Link>
            </p>
          </section>
        )}

        <ContactCta title={t('home.cta.title')} text={t('home.cta.text')} button={t('common.contactMe')} />
      </div>
    </div>
  )
}
