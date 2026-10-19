/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The legal pages' texts, English - the same sections as legalCs.ts. A DRAFT
// for a lawyer to read before launch. {{placeholders}} are filled from the
// provider details in backend/.env; a value that is not set shows as a dash.
import type { LegalSection } from './types'

const provider = [
  'Name: {{name}}',
  'Company ID (IČO): {{ico}}',
  'VAT ID (DIČ): {{dic}}',
  'Registered office / place of business: {{address}}',
  'Registration: {{registration}}',
  'Email: {{email}}',
  'Phone: {{phone}}',
]

export const legalEn: { privacy: LegalSection[]; terms: LegalSection[]; cookies: LegalSection[] } = {
  privacy: [
    {
      title: 'Who the controller is',
      items: provider,
      paragraphs: ['With questions about personal data, and to exercise your rights, you can contact me at {{dpoEmail}}.'],
    },
    {
      title: 'Contact form and email',
      paragraphs: [
        'If you write to me through the contact form or by email, I process your email address (and your name, if given) and the content of the message. The form sends the message by email; it does not store it in the website’s database.',
      ],
      items: [
        'Purpose: answering your enquiry and discussing a possible cooperation.',
        'Legal basis: steps taken at your request before entering into a contract and my legitimate interest in answering your enquiry (Art. 6(1)(b) and (f) GDPR).',
        'Retention: for as long as it takes to deal with the enquiry; if no cooperation follows, I delete the message within 12 months at the latest.',
      ],
    },
    {
      title: 'Cooperation and projects',
      paragraphs: [
        'If we agree to work together, I process your identification and contact details (and those of your employees, if relevant), details of the project and invoicing details. I keep them in a register of partners and projects that only the site administrator can access.',
      ],
      items: [
        'Purpose: performing the contract, communication during the project, invoicing, accounting and taxes.',
        'Legal basis: performance of a contract and compliance with a legal obligation (Art. 6(1)(b) and (c) GDPR).',
        'Retention: for the duration of the cooperation and then for the period that the law sets for accounting and tax documents.',
      ],
    },
    {
      title: 'Administrator sign-in',
      paragraphs: [
        'Only the site administrator can sign in. Visitors have no account and no data about them is processed for signing in. The administrator’s account is kept by the authorization service auth.withfbraun.com, which I run myself.',
      ],
    },
    {
      title: 'Server logs',
      paragraphs: [
        'The web server records technical data about every request – the IP address, the time, the requested address and the browser type. It serves the security and operation of the website (legitimate interest, Art. 6(1)(f) GDPR) and is kept only for as long as server logs are stored.',
      ],
    },
    {
      title: 'Who I share data with',
      paragraphs: [
        'I do not sell data or share it for marketing purposes. Only the providers of services I need to run things (hosting, email, an accountant or tax adviser) and public authorities, where the law requires it, may have access to it.',
        'If the provider of one of these services is based outside the European Economic Area, I will make sure the transfer is covered by standard contractual clauses or an adequacy decision.',
      ],
    },
    {
      title: 'Automated decision-making',
      paragraphs: ['There is no automated decision-making or profiling that would have legal effects.'],
    },
    {
      title: 'Your rights',
      paragraphs: ['You have the right to:'],
      items: [
        'access your personal data,',
        'have inaccurate data corrected,',
        'have data erased once the reason for processing has ceased,',
        'restrict the processing,',
        'data portability for data you have given me,',
        'object to processing based on legitimate interest,',
        'lodge a complaint with the Office for Personal Data Protection (www.uoou.gov.cz).',
      ],
    },
    {
      title: 'How to exercise your rights',
      paragraphs: ['Write to me at {{dpoEmail}}. I will reply within one month at the latest.'],
    },
    {
      title: 'Security',
      paragraphs: [
        'I protect data with appropriate technical and organizational measures, including encrypted transfer (HTTPS), restricted access and regular security fixes.',
      ],
    },
    {
      title: 'Cookies',
      paragraphs: ['The website uses no analytics or advertising cookies. See the Cookies page for details.'],
    },
    {
      title: 'Changes to this policy',
      paragraphs: ['I may update this policy. The version published on this page always applies, with its effective date.'],
    },
  ],
  terms: [
    {
      title: 'Website operator',
      items: provider,
    },
    {
      title: 'What this website is for',
      paragraphs: [
        'The website presents my services and experience. The information on it is for information only and is not an offer to enter into a contract. The price list is indicative.',
      ],
    },
    {
      title: 'Cooperation',
      paragraphs: [
        'Each project is governed by an individual contract or an accepted offer in which we agree the scope, the price, the schedule and the terms of operation.',
        'The price consists of a payment for the implementation and a service fee for operation. The service fee covers full operation of the solution, security fixes and small changes on request. Larger changes are always handled individually and specifically.',
        'Every solution is delivered with a content administration and documentation.',
      ],
    },
    {
      title: 'Website content',
      paragraphs: [
        'The texts and graphics of this website are protected by copyright. They may not be copied or distributed without my consent beyond the statutory exceptions. Links to third-party websites lead to content I am not responsible for.',
      ],
    },
    {
      title: 'Liability',
      paragraphs: [
        'I try to keep the information on the website correct and up to date, but I do not guarantee that it is complete. I am not liable for damage caused by using the information on the website unless the law provides otherwise.',
      ],
    },
    {
      title: 'Consumers',
      paragraphs: [
        'Where the client is a consumer, the relationship is also governed by the statutory consumer protection rules. A consumer has the right to out-of-court dispute resolution; the competent body is the Czech Trade Inspection Authority (www.coi.cz, adr.coi.cz).',
      ],
    },
    {
      title: 'Personal data',
      paragraphs: ['How I handle personal data is described in the privacy policy.'],
    },
    {
      title: 'Governing law and changes',
      paragraphs: [
        'The relationship is governed by the law of the Czech Republic. I may update these terms; the version published on this page applies, with its effective date.',
      ],
    },
  ],
  cookies: [
    {
      title: 'What the website stores',
      paragraphs: [
        'The website uses no analytics, marketing or third-party cookies. It only keeps a small amount of technical data in the browser’s local storage (localStorage), which is needed for the website to work and to remember your settings. No consent is required for such storage.',
      ],
    },
    {
      title: 'Overview',
      items: [
        'i18nextLng – the language you chose. Kept until you delete it.',
        'dark_mode – the light or dark mode you chose. Kept until you delete it.',
        'access_token, refresh_token – the administrator’s sign-in. Created only when the administrator signs in, never for visitors; removed on sign-out.',
      ],
    },
    {
      title: 'How to delete the data',
      paragraphs: ['You can delete local storage at any time in your browser’s settings. The website then falls back to its defaults.'],
    },
    {
      title: 'Changes',
      paragraphs: ['If the website ever starts using other storage or analytics, this page and the privacy policy will be updated first.'],
    },
  ],
}
