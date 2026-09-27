/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { ModuleDefinition } from '../modules/types'
import Footer from './Footer'
import LanguageDropdown from './LanguageDropdown'
import ThemeToggle from './ThemeToggle'

interface NavPage {
  heading: string
  slug: string
}

/** Open-book mark used for the nav badge (small) and the home page hero badge (large) - see BookIcon usages. */
function BookIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M12 5.5c-1.8-1.4-4.2-2-6.5-1.7v13c2.3-0.3 4.7 0.3 6.5 1.7 1.8-1.4 4.2-2 6.5-1.7v-13c-2.3-0.3-4.7 0.3-6.5 1.7z" />
      <path d="M12 5.5v13" />
    </svg>
  )
}

/**
 * Fixed, viewport-relative scattered shapes behind every page - the
 * "geometric confetti" identity. pointer-events-none + a negative z-index
 * keep it purely decorative; fixed (not absolute) so it reads as one
 * consistent backdrop rather than repeating or clipping per page.
 */
function ConfettiBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute left-[4%] top-[8%] h-11 w-11 rounded-full bg-mustard/40 dark:bg-mustard-dark/20" />
      <div className="absolute right-[7%] top-[4%] h-9 w-9 rotate-12 bg-teal/30 dark:bg-teal-dark/15" />
      <div className="absolute right-[3%] top-[28%] h-0 w-0 border-x-[26px] border-b-[45px] border-x-transparent border-b-coral/30 dark:border-b-coral-dark/15" />
      <div className="absolute left-[6%] top-[46%] h-7 w-7 rounded-full bg-violet/30 dark:bg-violet/15" />
      <div className="absolute right-[10%] bottom-[22%] h-10 w-10 -rotate-6 bg-mustard/35 dark:bg-mustard-dark/15" />
      <div className="absolute left-[8%] bottom-[10%] h-0 w-0 border-x-[22px] border-b-[38px] border-x-transparent border-b-teal/30 dark:border-b-teal-dark/15" />
      <div className="absolute right-[4%] bottom-[6%] h-8 w-8 rounded-full bg-coral/30 dark:bg-coral-dark/15" />
    </div>
  )
}

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

const iconButtonClass =
  'rounded-full p-1.5 text-ink-soft hover:bg-ink/10 hover:text-ink dark:text-ink-soft-dark dark:hover:bg-ink-dark/15 dark:hover:text-ink-dark'

function Nav({ modules }: { modules: ModuleDefinition[] }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [navPages, setNavPages] = useState<NavPage[]>([])
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const mobileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiFetch('/api/pages/')
      .then((r) => (r.ok ? r.json() : []))
      .then(setNavPages)
      .catch(() => {})
  }, [])

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
      {navPages.map((page) => (
        <Link key={page.slug} to={`/${page.slug}`} onClick={closeMobileMenu} className="hover:text-ink dark:hover:text-ink-dark">
          {page.heading}
        </Link>
      ))}
      {modules.flatMap((module) => module.nav ?? []).map((item) => (
        <Link key={item.to} to={item.to} onClick={closeMobileMenu} className="hover:text-ink dark:hover:text-ink-dark">{t(item.labelKey)}</Link>
      ))}
      {user?.is_admin && (
        <Link to="/admin" onClick={closeMobileMenu} className="hover:text-ink dark:hover:text-ink-dark">
          {t('nav.admin')}
        </Link>
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
          <Link to="/account" aria-label={t('common.account')} className={iconButtonClass}>
            <UserIcon className="h-5 w-5" />
          </Link>
          <button onClick={() => logout()} aria-label={t('common.logout')} className={iconButtonClass}>
            <LogoutIcon className="h-5 w-5" />
          </button>
        </>
      ) : (
        <Link to="/login" aria-label={t('common.login')} className={iconButtonClass}>
          <LoginIcon className="h-5 w-5" />
        </Link>
      )}
      <LanguageDropdown />
      <ThemeToggle />
    </>
  )

  return (
    <header className="border-b border-ink/10 dark:border-ink-dark/10">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3 text-sm text-ink-soft dark:text-ink-soft-dark">
        <Link to="/" className="flex items-center gap-3 text-ink hover:opacity-80 dark:text-ink-dark">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal text-white">
            <BookIcon className="h-6 w-6" />
          </span>
          <span className="font-display font-bold leading-tight">{t('nav.brand')}</span>
        </Link>

        <nav className="hidden items-center gap-4 md:flex">
          {navLinks}
        </nav>

        <div className="flex items-center gap-2">
          {utilityControls}
          <button type="button" onClick={() => setMobileMenuOpen((open) => !open)} aria-label={t(mobileMenuOpen ? 'common.closeMenu' : 'common.openMenu')} aria-expanded={mobileMenuOpen}
            className="inline-flex items-center justify-center rounded-lg p-2 text-ink-soft hover:bg-ink/10 dark:text-ink-soft-dark dark:hover:bg-ink-dark/15 md:hidden">
            {mobileMenuOpen ? <CloseIcon className="h-6 w-6" /> : <MenuIcon className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div ref={mobileMenuRef} className="border-t border-ink/10 px-6 py-3 dark:border-ink-dark/10 md:hidden">
          <nav className="flex flex-col items-start gap-3 text-sm text-ink-soft dark:text-ink-soft-dark">
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
    <div className="relative flex min-h-screen flex-col text-ink dark:text-ink-dark">
      <ConfettiBackground />
      <Nav modules={modules} />
      <main className="page flex-1">{children}</main>
      <Footer />
    </div>
  )
}
