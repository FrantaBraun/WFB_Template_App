/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Navigate } from 'react-router-dom'
import type { ModuleDefinition } from '../types'
import ContactPage from './ContactPage'

const contactFormModule: ModuleDefinition = {
  key: 'kontaktni_formular',
  // The page lives at /contact; /kontakt was its first address and stays as a
  // redirect so links already out there keep working.
  routes: [
    { path: '/contact', element: <ContactPage /> },
    { path: '/kontakt', element: <Navigate to="/contact" replace /> },
  ],
  nav: [{ to: '/contact', labelKey: 'kontaktni_formular:nav.contact' }],
  locales: {
    cs: {
      nav: { contact: 'Kontakt' },
      page: {
        title: 'Kontaktní formulář',
        metaDescription: 'Napište nám zprávu přes kontaktní formulář.',
        detailsHeading: 'Kontaktní údaje',
        emailDetail: 'E-mail',
        addressDetail: 'Adresa',
        githubDetail: 'GitHub',
        linkedinDetail: 'LinkedIn',
        subjectLabel: 'Předmět',
        messageLabel: 'Zpráva',
        emailLabel: 'Váš e-mail (pro odpověď)',
        signedInAs: 'Odesíláte jako {{name}}',
        submit: 'Odeslat',
        submitting: 'Odesílání…',
        error: 'Odeslání se nezdařilo. Zkuste to prosím znovu.',
        thanksTitle: 'Děkujeme za zprávu!',
        thanksMessage: 'Ozveme se vám co nejdříve.',
        backHome: 'Zpět na hlavní stránku',
      },
    },
    en: {
      nav: { contact: 'Contact' },
      page: {
        title: 'Contact form',
        metaDescription: 'Send us a message through the contact form.',
        detailsHeading: 'Contact details',
        emailDetail: 'Email',
        addressDetail: 'Address',
        githubDetail: 'GitHub',
        linkedinDetail: 'LinkedIn',
        subjectLabel: 'Subject',
        messageLabel: 'Message',
        emailLabel: 'Your email (for a reply)',
        signedInAs: 'Sending as {{name}}',
        submit: 'Send',
        submitting: 'Sending…',
        error: 'Failed to send. Please try again.',
        thanksTitle: 'Thank you for your message!',
        thanksMessage: "We'll get back to you as soon as possible.",
        backHome: 'Back to homepage',
      },
    },
  },
}

export default contactFormModule
