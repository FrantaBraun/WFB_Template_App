/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import usePageMeta from '../../hooks/usePageMeta'
import { card, ContactCta, mutedText, PageShell, Section, textLink } from './ui'

function Texts({ keyPrefix }: { keyPrefix: string }) {
  const { t } = useTranslation('freelancer')
  const paragraphs = t(`${keyPrefix}.paragraphs`, { returnObjects: true }) as string[]
  return (
    <div className="max-w-2xl space-y-4">
      {paragraphs.map((paragraph) => (
        <p key={paragraph} className={mutedText}>
          {paragraph}
        </p>
      ))}
    </div>
  )
}

/** The person behind the site: what they do, who they like working for, and how they use AI. */
export default function AboutPage() {
  const { t } = useTranslation('freelancer')
  usePageMeta({ title: t('about.metaTitle'), description: t('about.metaDescription') })

  return (
    <PageShell title={t('about.title')} lead={t('about.lead')}>
      <Section title={t('about.experience.title')}>
        <Texts keyPrefix="about.experience" />
      </Section>

      <Section title={t('about.why.title')}>
        <Texts keyPrefix="about.why" />
      </Section>

      <section className={`${card} sm:p-8`}>
        <h2 className="text-2xl font-semibold tracking-tight">{t('about.ai.title')}</h2>
        <div className="mt-4">
          <Texts keyPrefix="about.ai" />
        </div>
      </section>

      <Section title={t('about.beyond.title')}>
        <Texts keyPrefix="about.beyond" />
        <p className="mt-4">
          <a href="https://www.withfbraun.com" target="_blank" rel="noopener noreferrer" className={textLink}>
            {t('about.beyond.link')} ↗
          </a>
        </p>
      </Section>

      <ContactCta title={t('about.cta.title')} text={t('about.cta.text')} button={t('common.contactMe')} />
    </PageShell>
  )
}
