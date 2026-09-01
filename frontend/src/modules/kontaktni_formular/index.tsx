/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ModuleDefinition } from '../types'
import ContactPage from './ContactPage'

const contactFormModule: ModuleDefinition = {
  key: 'kontaktni_formular',
  routes: [{ path: '/kontakt', element: <ContactPage /> }],
  nav: [{ to: '/kontakt', labelKey: 'kontaktni_formular:nav.contact' }],
  locales: {
    cs: {
      nav: { contact: 'Kontakt' },
      page: {
        title: 'Kontaktní formulář',
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
