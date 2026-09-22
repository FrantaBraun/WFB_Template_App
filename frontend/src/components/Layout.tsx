/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { SUPPORTED_LANGUAGES } from '../i18n'
import type { ModuleDefinition } from '../modules/types'
import Footer from './Footer'
import ThemeToggle from './ThemeToggle'

/** Hamburger glyph, hand-drawn to match ThemeToggle.tsx's inline-SVG icon style rather than pulling in an icon library. */
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

/** Top navigation bar: brand link, any enabled module's own nav links, plus auth-aware links (account/logout when signed in, login/register otherwise). Collapses into a hamburger-triggered dropdown below the `md` breakpoint, where the full link row would otherwise overflow the header and overlap the brand. */
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
      {user ? (
        <>
          <Link to="/account" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.account')}
          </Link>
          <button
            onClick={() => {
              logout()
              closeMobileMenu()
            }}
            className="text-left hover:text-slate-900 dark:hover:text-slate-100"
          >
            {t('common.logout')}
          </button>
        </>
      ) : (
        <>
          <Link to="/login" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.login')}
          </Link>
          <Link to="/register" onClick={closeMobileMenu} className="hover:text-slate-900 dark:hover:text-slate-100">
            {t('common.register')}
          </Link>
        </>
      )}
    </>
  )

  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3 text-sm text-slate-600 dark:text-slate-300">
        <Link to="/" className="tracking-tight text-stone-800 hover:text-stone-600 dark:text-stone-200 dark:hover:text-stone-300 flex">
          <img src="/logo.png" alt="" className="mx-1 bg-slate-200 rounded" width={40} />
          <span className='font-extrabold'>{t('nav.brand')}</span>
          <span className='ms-1 text-stone-500 dark:text-stone-400 text-xs pt-4' style={{marginLeft: "-15px"}}>WFB</span>
        </Link>

        <nav className="hidden items-center gap-4 md:flex">
          {navLinks}
          <LanguageSwitcher />
          <ThemeToggle />
        </nav>

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

      {mobileMenuOpen && (
        <div ref={mobileMenuRef} className="border-t border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-950 md:hidden">
          <nav className="flex flex-col items-start gap-3">
            {navLinks}
            <div className="flex items-center gap-3 pt-1">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
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
