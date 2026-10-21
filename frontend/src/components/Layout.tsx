/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { ModuleDefinition } from '../modules/types'
import Footer from './Footer'
import LanguageDropdown from './LanguageDropdown'
import NotificationBell from './NotificationBell'
import ThemeToggle from './ThemeToggle'

/** Hamburger glyph, hand-drawn to match ThemeToggle.tsx's inline-SVG icon style rather than pulling in an icon library. */
const isRegistrationAllowed = (import.meta.env.VITE_REGISTRATION_ALLOWED || 'true') === 'true';

function MenuIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  )
}

/** Close ("X") glyph shown in place of MenuIcon while the mobile menu is open. */
function CloseIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

function LoginIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" />
    </svg>
  )
}

function LogoutIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  )
}

const iconButtonClass =
  'rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'

/**
 * Top navigation bar: brand link, page links (any enabled module's own nav
 * links plus this app's API Docs / Collections, and Teams / Integrations
 * when signed in) that collapse into a hamburger-triggered dropdown below
 * the `md` breakpoint, and utility controls (notifications, account,
 * login/logout, language, theme) that stay visible at every width.
 */
function Nav({ modules }: { modules: ModuleDefinition[] }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const mobileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!mobileMenuOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (mobileMenuRef.current && !mobileMenuRef.current.contains(e.target as Node)) {
        setMobileMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [mobileMenuOpen])

  function closeMobileMenu() {
    setMobileMenuOpen(false)
  }

  const navLinks = (
    <>
      {modules.flatMap((module) => module.nav ?? []).map((item) => (
        <Link key={item.to} to={item.to} onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
          {t(item.labelKey)}
        </Link>
      ))}
      {/* Unconditional, unlike the Teams link below - public browsing works while logged out. */}
      <Link to="/api-docs" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
        {t('common.apiDocs')}
      </Link>
      <Link to="/collections" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
        {t('common.collections')}
      </Link>
      {user && (
        <>
          <Link to="/teams" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.teams')}
          </Link>
          <Link to="/integrations" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.integrations')}
          </Link>
        </>
      )}
    </>
  )

  const utilityControls = (
    <>
      {modules.filter((module) => module.headerWidget).map((module) => (
        <span key={module.key}>{module.headerWidget}</span>
      ))}
      {user ? (
        <>
          <NotificationBell />
          <Link to="/account" aria-label={t('common.account')} className={iconButtonClass}>
            <UserIcon className="h-5 w-5" />
          </Link>
          <button onClick={() => logout()} aria-label={t('common.logout')} className={iconButtonClass}>
            <LogoutIcon className="h-5 w-5" />
          </button>
        </>
      ) : (
<<<<<<< HEAD
        <Link to="/login" aria-label={t('common.login')} className={iconButtonClass}>
=======
        isRegistrationAllowed &&
        <Link to="/login" aria-label={t('common.login')} className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100">
>>>>>>> core
          <LoginIcon className="h-5 w-5" />
        </Link>
      )}
      <LanguageDropdown />
      <ThemeToggle />
    </>
  )

  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-1 px-3 py-3 text-sm text-slate-600 dark:text-slate-300 sm:gap-2 sm:px-6">
        <Link to="/" aria-label={t('nav.brand')} className="tracking-tight text-stone-800 hover:text-stone-600 dark:text-stone-200 dark:hover:text-stone-300 flex min-w-0">
          <img src="/logo.png" alt="" className="mx-1 shrink-0 bg-slate-200 rounded max-sm:w-8" width={40} />
          {/* On phones the icon cluster keeps its size, so the name truncates (and drops out below 360px) and the WFB tag hides. */}
          <span className='hidden min-w-0 self-center truncate font-extrabold min-[360px]:block sm:self-auto'>{t('nav.brand')}</span>
          <span className='ms-1 hidden text-stone-500 dark:text-stone-400 text-xs pt-4 sm:block' style={{marginLeft: "-15px"}}>WFB</span>
        </Link>

        <nav className="hidden items-center gap-4 md:flex">
          {navLinks}
        </nav>

        <div className="flex shrink-0 items-center gap-0.5 sm:gap-2">
          {utilityControls}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((open) => !open)}
            aria-label={t(mobileMenuOpen ? 'common.closeMenu' : 'common.openMenu')}
            aria-expanded={mobileMenuOpen}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 md:hidden"
          >
            {mobileMenuOpen ? <CloseIcon className="h-6 w-6" /> : <MenuIcon className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div ref={mobileMenuRef} className="border-t border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950 sm:px-6 md:hidden">
          <nav className="flex flex-col items-start gap-3">
            {navLinks}
          </nav>
        </div>
      )}
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
