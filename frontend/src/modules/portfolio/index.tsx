/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Portfolio: /portfolio (public list of cards), /portfolio/:slug (a project's
// own page) and the administrator's /portfolio/manage area (list with order and
// visibility, /new and /:id form). There is deliberately no `nav` entry: the
// site that uses the module declares the header link itself (its own place in
// the menu), pointing at this module's `portfolio:nav.portfolio` label.
//
// `/portfolio/manage` is a static segment, so react-router ranks it above the
// dynamic `/portfolio/:slug` whatever the order below; the backend also refuses
// "manage" as a slug, so no project can ever be shadowed by the editor's list.
import type { ModuleDefinition } from '../types'
import ItemFormPage from './ItemFormPage'
import { cs, en } from './locales'
import ManagePage from './ManagePage'
import PortfolioDetailPage from './PortfolioDetailPage'
import PortfolioPage from './PortfolioPage'

const portfolioModule: ModuleDefinition = {
  key: 'portfolio',
  routes: [
    { path: '/portfolio', element: <PortfolioPage /> },
    { path: '/portfolio/manage', element: <ManagePage /> },
    { path: '/portfolio/manage/new', element: <ItemFormPage /> },
    { path: '/portfolio/manage/:id', element: <ItemFormPage /> },
    { path: '/portfolio/:slug', element: <PortfolioDetailPage /> },
  ],
  locales: { cs, en },
}

export default portfolioModule
