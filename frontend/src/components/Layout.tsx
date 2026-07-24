/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { SUPPORTED_LANGUAGES } from '../i18n'
import { persistDarkModePreference } from '../theme'

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

/**
 * Light/dark toggle switch. Applies the theme instantly (via ThemeContext)
 * and, when signed in, immediately persists it to the profile too - there's
 * no separate "save" step for this control, unlike the rest of the Profile
 * form on the Account page.
 */
function ThemeToggle() {
  const { t } = useTranslation()
  const { darkMode, setDarkMode } = useTheme()
  const { user } = useAuth()

  function handleToggle() {
    const next = !darkMode
    setDarkMode(next)
    if (user?.application_group_id) {
      persistDarkModePreference(user.application_group_id, next)
    }
  }

  return (
    <button
      onClick={handleToggle}
      role="switch"
      aria-checked={darkMode}
      aria-label={t('common.toggleDarkMode')}
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
        darkMode ? 'bg-sky-600' : 'bg-slate-300 dark:bg-slate-700'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          darkMode ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

/** Top navigation bar: brand link plus auth-aware links (account/logout when signed in, login/register otherwise). */
function Nav() {
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
          {user ? (
            <>
              <Link to="/account" className="hover:text-slate-900 dark:hover:text-slate-100">
                {t('common.account')}
              </Link>
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

/** Page chrome shared by every route: renders Nav above the routed page content. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main className="page">{children}</main>
    </>
  )
}
