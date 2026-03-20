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
  const googleClientId = process.env.GOOGLE_CLIENT_ID || process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

  return (
    <html lang={resolvedLocale}>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        {googleClientId ? (
          <meta name="google-signin-client_id" content={googleClientId} />
        ) : null}
      </head>
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
