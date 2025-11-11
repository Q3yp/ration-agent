'use client'

import { useState } from 'react'
import { useI18n } from '@/contexts/I18nContext'
import { supportedLocales, getLocaleName, Locale } from '@/lib/i18n/locales'

const LOCALE_SEQUENCE: Locale[] = supportedLocales

export function LocaleToggle() {
  const { locale, setLocale } = useI18n()
  const [pending, setPending] = useState(false)

  const handleSelect = async (target: Locale) => {
    if (target === locale || pending) {
      return
    }
    setPending(true)
    try {
      await setLocale(target)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="inline-flex items-center rounded-md border bg-background p-0.5 shadow-sm">
      {LOCALE_SEQUENCE.map((loc, index) => {
        const isActive = loc === locale
        const label = getLocaleName(loc, locale)
        return (
          <button
            key={loc}
            type="button"
            disabled={pending}
            onClick={() => handleSelect(loc)}
            className={[
              'px-3 py-1 text-xs font-medium transition-colors duration-150 whitespace-nowrap',
              index === 0 ? 'rounded-l-md' : '',
              index === LOCALE_SEQUENCE.length - 1 ? 'rounded-r-md' : '',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-primary'
            ].join(' ')}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
