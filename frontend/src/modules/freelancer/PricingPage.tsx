/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import usePageMeta from '../../hooks/usePageMeta'
import { useProvider } from './legal/useProvider'
import { card, ContactCta, mutedText, PageShell, Section } from './ui'

interface Plan {
  title: string
  price: string
  servicePrice: string
  features: string[]
}

/**
 * How the price is made up: a one-off payment for the implementation plus a
 * service fee for operation, and how it is paid. The amounts come from the
 * locale files and are invented placeholders for now - the note below says so
 * on the page itself until the real price list replaces them.
 */
export default function PricingPage() {
  const { t } = useTranslation('freelancer')
  usePageMeta({ title: t('pricing.metaTitle'), description: t('pricing.metaDescription') })
  const provider = useProvider()

  const plans = t('pricing.implementation.plans', { returnObjects: true }) as Plan[]
  const serviceItems = t('pricing.service.items', { returnObjects: true }) as string[]
  const financingItems = t('pricing.financing.items', { returnObjects: true }) as string[]

  return (
    <PageShell title={t('pricing.title')} lead={t('pricing.lead')}>
      <p role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        {t('pricing.placeholderNote')}
      </p>

      <Section title={t('pricing.implementation.title')} intro={t('pricing.implementation.intro')}>
        <ul className="grid gap-4 md:grid-cols-3">
          {plans.map((plan) => (
            <li key={plan.title} className={`${card} flex flex-col`}>
              <h3 className="text-lg font-semibold">{plan.title}</h3>
              <p className="mt-4">
                <span className={`text-sm ${mutedText}`}>{t('pricing.implementation.from')} </span>
                <span className="text-2xl font-semibold tracking-tight">{plan.price}</span>
              </p>
              <p className={`text-sm ${mutedText}`}>{t('pricing.implementation.once')}</p>
              <ul className="mt-4 flex-1 space-y-2 text-sm">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex gap-3">
                    <span aria-hidden="true" className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600 dark:bg-violet-400" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-5 border-t border-slate-200 pt-4 text-sm dark:border-slate-800">
                <span className={mutedText}>
                  {t('pricing.implementation.service')} {t('pricing.implementation.from')}{' '}
                </span>
                <span className="font-semibold">{plan.servicePrice}</span>
                <span className={mutedText}> {t('pricing.implementation.perMonth')}</span>
              </p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t('pricing.service.title')} intro={t('pricing.service.intro')}>
        <ul className="space-y-2">
          {serviceItems.map((item) => (
            <li key={item} className="flex gap-3">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600 dark:bg-violet-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <p className={`mt-4 max-w-2xl ${mutedText}`}>{t('pricing.service.outro')}</p>
      </Section>

      <Section title={t('pricing.financing.title')}>
        <ul className="space-y-2">
          {financingItems.map((item) => (
            <li key={item} className="flex gap-3">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600 dark:bg-violet-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        {/* Said only once the provider's own details are in place: until then it would state a VAT status nobody has confirmed. */}
        {provider?.configured && <p className={`mt-4 text-sm ${mutedText}`}>{t(provider.vat_payer ? 'pricing.vatPayer' : 'pricing.notVatPayer')}</p>}
      </Section>

      <ContactCta title={t('pricing.cta.title')} text={t('pricing.cta.text')} button={t('common.contactMe')} />
    </PageShell>
  )
}
