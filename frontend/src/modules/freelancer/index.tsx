/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The pages of the freelancer's own website: services, pricing, about me and
// the legal pages (the home page is src/pages/HomePage.tsx, which re-exports
// ./HomePage). The header navigation is built from the enabled modules in
// folder-name order, so this module - "f" - comes before kontaktni_formular, and
// it declares the portfolio link itself (the portfolio module has no nav of its
// own): that is what puts Contact last. Rename the folder and the order changes.
import type { ModuleDefinition } from '../types'
import AboutPage from './AboutPage'
import { CookiesPage, PrivacyPage, TermsPage } from './legal/pages'
import { csBundle, enBundle } from './locales'
import PricingPage from './PricingPage'
import ServicesPage from './ServicesPage'

const freelancerModule: ModuleDefinition = {
  key: 'freelancer',
  routes: [
    { path: '/about', element: <AboutPage /> },
    { path: '/services', element: <ServicesPage /> },
    { path: '/pricing', element: <PricingPage /> },
    { path: '/privacy', element: <PrivacyPage /> },
    { path: '/terms', element: <TermsPage /> },
    { path: '/cookies', element: <CookiesPage /> },
  ],
  nav: [
    { to: '/services', labelKey: 'freelancer:nav.services' },
    { to: '/portfolio', labelKey: 'portfolio:nav.portfolio' },
    { to: '/pricing', labelKey: 'freelancer:nav.pricing' },
    { to: '/about', labelKey: 'freelancer:nav.about' },
  ],
  footerLinks: [
    { to: '/privacy', labelKey: 'freelancer:footer.privacy' },
    { to: '/terms', labelKey: 'freelancer:footer.terms' },
    { to: '/cookies', labelKey: 'freelancer:footer.cookies' },
  ],
  locales: { cs: csBundle, en: enBundle },
}

export default freelancerModule
