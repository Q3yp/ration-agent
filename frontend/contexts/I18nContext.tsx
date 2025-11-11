'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { defaultLocale, formatTranslation, getRawTranslation, Locale, supportedLocales } from '@/lib/i18n/locales'
import { getAuthHeaders } from '@/utils/authHeaders'

interface SetLocaleOptions {
  notifyServer?: boolean
}

interface I18nContextValue {
  locale: Locale
  t: (key: string, params?: Record<string, string | number>) => string
  tRaw: (key: string) => string | string[] | undefined
  setLocale: (next: Locale, options?: SetLocaleOptions) => Promise<void>
  formatRelativeTime: (value: Date | string | number) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

async function updateServerLocale(locale: Locale) {
  try {
    const response = await fetch('/auth/users/me/preferences', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ preferred_language: locale }),
    })

    if (!response.ok && response.status !== 401) {
      throw new Error('Failed to update locale')
    }
  } catch (error) {
    console.warn('Failed to update preferred language:', error)
  }
}

function relativeFormatter(locale: Locale) {
  return new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
}

export function I18nProvider({
  initialLocale = defaultLocale,
  children,
}: {
  initialLocale?: Locale
  children: React.ReactNode
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale)

  useEffect(() => {
    document.documentElement.lang = locale
    document.cookie = `app_locale=${locale}; path=/; max-age=${60 * 60 * 24 * 365}`
  }, [locale])

  const setLocale = useCallback(async (next: Locale, options?: SetLocaleOptions) => {
    if (!supportedLocales.includes(next)) return
    setLocaleState(next)

    if (options?.notifyServer === false) {
      return
    }

    await updateServerLocale(next)
  }, [])

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => formatTranslation(locale, key, params),
    [locale]
  )

  const tRaw = useCallback(
    (key: string) => getRawTranslation(locale, key),
    [locale]
  )

  const formatRelativeTime = useCallback((value: Date | string | number) => {
    const formatter = relativeFormatter(locale)
    const date = value instanceof Date ? value : new Date(value)
    const diffMs = date.getTime() - Date.now()
    const diffSeconds = Math.round(diffMs / 1000)

    if (Math.abs(diffSeconds) < 60) {
      return formatter.format(Math.round(diffSeconds), 'seconds')
    }

    const diffMinutes = Math.round(diffSeconds / 60)
    if (Math.abs(diffMinutes) < 60) {
      return formatter.format(diffMinutes, 'minutes')
    }

    const diffHours = Math.round(diffMinutes / 60)
    if (Math.abs(diffHours) < 24) {
      return formatter.format(diffHours, 'hours')
    }

    const diffDays = Math.round(diffHours / 24)
    return formatter.format(diffDays, 'days')
  }, [locale])

  const value = useMemo(() => ({
    locale,
    t,
    tRaw,
    setLocale,
    formatRelativeTime,
  }), [locale, t, tRaw, setLocale, formatRelativeTime])

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider')
  }
  return context
}
