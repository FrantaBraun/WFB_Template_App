/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { SUPPORTED_LANGUAGES } from '../i18n'
import type { ModuleDefinition } from '../modules/types'
import Footer from './Footer'
import NotificationBell from './NotificationBell'
import ThemeToggle from './ThemeToggle'

/** Small control to switch the active i18next language between the supported locales. */
function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <div className="flex items-center gap-1 text-xs uppercase tracking-wide text-slate-500">
      {SUPPORTED_LANGUAGES.map((lng) => (
        <button
          key={lng}
          onClick={() => i18n.changeLanguage(lng)}
          className={`rounded px-1.5 py-0.5 ${
            i18n.resolvedLanguage === lng
              ? 'bg-slate-200 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
              : 'hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          {lng}
        </button>
      ))}
    </div>
  )
}

/** Top navigation bar: brand link, any enabled module's own nav links, plus auth-aware links (account/logout when signed in, login/register otherwise). */
function Nav({ modules }: { modules: ModuleDefinition[] }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()

  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3 text-sm text-slate-600 dark:text-slate-300">
        <Link to="/" className="tracking-tight text-stone-800 hover:text-stone-600 dark:text-stone-200 dark:hover:text-stone-300 flex">
          <img src="/logo.png" alt="" className="mx-1 bg-slate-200 rounded" width={40} />
          <span className='font-extrabold'>{t('nav.brand')}</span>
          <span className='ms-1 text-stone-500 dark:text-stone-400 text-xs pt-4' style={{marginLeft: "-15px"}}>WFB</span>
        </Link>

        <nav className="flex items-center gap-4">
          {modules.flatMap((module) => module.nav ?? []).map((item) => (
            <Link key={item.to} to={item.to} className="hover:text-slate-900 dark:hover:text-slate-100">
              {t(item.labelKey)}
            </Link>
          ))}
          {/* Unconditional, unlike the Teams link below - public browsing works while logged out. */}
          <Link to="/api-docs" className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.apiDocs')}
          </Link>
          {user ? (
            <>
              <Link to="/teams" className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.teams')}
              </Link>
              <Link to="/account" className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.account')}
              </Link>
              <NotificationBell />
              <button onClick={() => logout()} className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.logout')}
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.login')}
              </Link>
              <Link to="/register" className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.register')}
              </Link>
            </>
          )}
          <LanguageSwitcher />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}

/**
 * Page chrome shared by every route: Nav above the routed page content, Footer
 * below it. The flex column + min-h-screen wrapper with flex-1 on <main> is
 * what pins the footer to the bottom of the viewport even when a page's own
 * content is shorter than the screen, while still flowing normally (footer
 * right after the content, page scrolls) once content grows past that.
 */
export default function Layout({ children, modules = [] }: { children: React.ReactNode; modules?: ModuleDefinition[] }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav modules={modules} />
      <main className="page flex-1">{children}</main>
      <Footer />
    </div>
  )
}
