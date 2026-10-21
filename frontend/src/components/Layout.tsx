/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { ModuleDefinition } from '../modules/types'
import Footer from './Footer'
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

  // Nav items are pills; the page the reader is on is filled in.
  const navLinks = (
    <>
      {modules
        .flatMap((module) => module.nav ?? [])
        .filter((item) => !item.requiresLogin || user)
        .map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={closeMobileMenu}
            className={({ isActive }) =>
              `rounded-full px-3 py-1.5 font-medium transition ${
                isActive
                  ? 'bg-violet-100 text-violet-800 dark:bg-violet-500/20 dark:text-violet-200'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
              }`
            }
          >
            {t(item.labelKey)}
          </NavLink>
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
    <header className="border-b border-t-4 border-slate-200 border-t-violet-600 bg-white dark:border-slate-800 dark:border-t-violet-500 dark:bg-slate-950">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-1 px-3 py-3 text-sm text-slate-600 dark:text-slate-300 sm:gap-2 sm:px-6">
        <Link to="/" aria-label={t('nav.brand')} className="tracking-tight text-stone-800 hover:text-stone-600 dark:text-stone-200 dark:hover:text-stone-300 flex min-w-0">
          <img src="/logo.png" alt="" className="mx-1 shrink-0 bg-slate-200 rounded max-sm:w-8" width={40} />
          {/* On phones the icon cluster keeps its size, so the name truncates (and drops out below 360px) and the WFB tag hides. */}
          <span className='hidden min-w-0 self-center truncate font-extrabold min-[360px]:block sm:self-auto'>{t('nav.brand')}</span>
          <span className='ms-1 hidden text-stone-500 dark:text-stone-400 text-xs pt-4 sm:block' style={{marginLeft: "-15px"}}>WFB</span>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex">
          {navLinks}
        </nav>

        <div className="flex shrink-0 items-center gap-0.5 sm:gap-2">
          {utilityControls}
          <button type="button" onClick={() => setMobileMenuOpen((open) => !open)} aria-label={t(mobileMenuOpen ? 'common.closeMenu' : 'common.openMenu')} aria-expanded={mobileMenuOpen}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 lg:hidden">
            {mobileMenuOpen ? <CloseIcon className="h-6 w-6" /> : <MenuIcon className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div ref={mobileMenuRef} className="border-t border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950 sm:px-6 lg:hidden">
          <nav className="flex flex-col items-start gap-1 text-sm">
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
