import type { Metadata } from 'next'
import { cookies, headers } from 'next/headers'
import './globals.css'
import { AuthProvider } from '@/contexts/AuthContext'
import { I18nProvider } from '@/contexts/I18nContext'
import { defaultLocale, Locale, supportedLocales, detectLocaleFromHeader } from '@/lib/i18n/locales'

export const metadata: Metadata = {
  title: 'Huitu Nutrition Copilot',
  description: 'AI nutrition copilot for dairy, beef, and companion animals powered by LangGraph and Claude.',
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const cookieLocale = cookieStore.get('app_locale')?.value as Locale | undefined
  let initialLocale: Locale | undefined = cookieLocale && supportedLocales.includes(cookieLocale)
    ? cookieLocale
    : undefined

  if (!initialLocale) {
    const headerList = await headers()
    const acceptLanguage = headerList.get('accept-language')
    initialLocale = detectLocaleFromHeader(acceptLanguage)
  }

  const resolvedLocale = initialLocale ?? defaultLocale

  return (
    <html lang={resolvedLocale}>
      <body className="antialiased">
        <I18nProvider initialLocale={resolvedLocale}>
          <AuthProvider>
            {children}
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  )
}
