/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import usePageMeta from '../../hooks/usePageMeta'
import { JsonLd } from './seo'
import { card, ContactCta, mutedText, PageShell, Section } from './ui'

interface Service {
  title: string
  text: string
  points: string[]
}

interface Step {
  title: string
  text: string
}

/** What is offered, in detail, and how a project goes from first talk to operation. */
export default function ServicesPage() {
  const { t } = useTranslation('freelancer')
  usePageMeta({ title: t('services.metaTitle'), description: t('services.metaDescription') })

  const services = t('services.items', { returnObjects: true }) as Service[]
  const steps = t('services.process.steps', { returnObjects: true }) as Step[]

  return (
    <PageShell title={t('services.title')} lead={t('services.lead')}>
      <JsonLd
        id="services"
        data={{
          '@context': 'https://schema.org',
          '@type': 'ItemList',
          itemListElement: services.map((service, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            item: { '@type': 'Service', name: service.title, description: service.text },
          })),
        }}
      />

      <div className="grid gap-5">
        {services.map((service) => (
          <section key={service.title} className={`${card} sm:p-8`}>
            <h2 className="text-xl font-semibold tracking-tight">{service.title}</h2>
            <p className={`mt-3 max-w-2xl ${mutedText}`}>{service.text}</p>
            <ul className="mt-4 space-y-2">
              {service.points.map((point) => (
                <li key={point} className="flex gap-3">
                  <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600 dark:bg-violet-400" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <Section title={t('services.process.title')}>
        <ol className="space-y-5">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span
                aria-hidden="true"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-100 font-semibold text-violet-800 dark:bg-violet-950 dark:text-violet-200"
              >
                {index + 1}
              </span>
              <div>
                <h3 className="font-semibold">{step.title}</h3>
                <p className={`mt-1 ${mutedText}`}>{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <ContactCta title={t('services.cta.title')} text={t('services.cta.text')} button={t('common.contactMe')} />
    </PageShell>
  )
}
