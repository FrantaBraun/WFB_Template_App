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
import { PubLogo } from './PubGraphics'
import LanguageDropdown from './LanguageDropdown'
import ThemeToggle from './ThemeToggle'

const isRegistrationAllowed = (import.meta.env.VITE_REGISTRATION_ALLOWED || 'true') === 'true';

function MenuIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  )
}

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

function Nav({ modules }: { modules: ModuleDefinition[] }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const mobileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!mobileMenuOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (mobileMenuRef.current && !mobileMenuRef.current.contains(e.target as Node)) setMobileMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [mobileMenuOpen])

  function closeMobileMenu() { setMobileMenuOpen(false) }

  const navLinks = (
    <>
      <Link to="/o-nas" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">{t('nav.about')}</Link>
      {modules.flatMap((module) => module.nav ?? []).map((item) => (
        <Link key={item.to} to={item.to} onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">{t(item.labelKey)}</Link>
      ))}
    </>
  )

  const utilityControls = (
    <>
      {modules.filter((module) => module.headerWidget).map((module) => (
        <span key={module.key}>{module.headerWidget}</span>
      ))}
      {user ? (
        <>
          <Link to="/account" aria-label={t('common.account')} className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100">
            <UserIcon className="h-5 w-5" />
          </Link>
          <button onClick={() => logout()} aria-label={t('common.logout')} className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100">
            <LogoutIcon className="h-5 w-5" />
          </button>
        </>
      ) : (
        isRegistrationAllowed &&
        <Link to="/login" aria-label={t('common.login')} className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100">
          <LoginIcon className="h-5 w-5" />
        </Link>
      )}
      <LanguageDropdown />
      <ThemeToggle />
    </>
  )

  return (
    <header className="border-b border-t-[3px] border-slate-200 border-t-hop bg-white dark:border-slate-800 dark:border-t-hop-dark dark:bg-slate-950">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-1 px-3 py-3 text-sm text-slate-600 dark:text-slate-300 sm:gap-2 sm:px-6">
        <Link to="/" aria-label={t('nav.brand')} className="flex min-w-0 items-center gap-2 text-slate-900 hover:text-hop dark:text-slate-100 dark:hover:text-beer-dark">
          <PubLogo className="h-9 w-9 shrink-0" />
          {/* On phones the icon cluster keeps its size, so the name truncates (and drops out below 360px). */}
          <span className="font-display hidden min-w-0 truncate text-base tracking-wide min-[360px]:block sm:text-lg">{t('nav.brand')}</span>
        </Link>

        <nav className="hidden items-center gap-4 md:flex">
          {navLinks}
        </nav>

        <div className="flex shrink-0 items-center gap-0.5 sm:gap-2">
          {utilityControls}
          <button type="button" onClick={() => setMobileMenuOpen((open) => !open)} aria-label={t(mobileMenuOpen ? 'common.closeMenu' : 'common.openMenu')} aria-expanded={mobileMenuOpen}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 md:hidden">
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

export default function Layout({ children, modules = [] }: { children: React.ReactNode; modules?: ModuleDefinition[] }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav modules={modules} />
      <main className="page flex-1">{children}</main>
      <Footer />
    </div>
  )
}
