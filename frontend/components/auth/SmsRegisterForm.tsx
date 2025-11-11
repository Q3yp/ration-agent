'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { supportedLocales, getLocaleName, Locale } from '@/lib/i18n/locales'
import { useI18n } from '@/contexts/I18nContext'

type RegisterPayload = {
  mobile: string
  code: string
  password: string
  username?: string
  preferred_language?: Locale
}

interface SmsRegisterFormProps {
  onRequestCode: (mobile: string) => Promise<{ message: string; expires_in: number }>
  onRegister: (payload: RegisterPayload) => Promise<void>
  onClearError?: () => void
  isSubmitting: boolean
  error?: string | null
  defaultLocale: Locale
}

const RESEND_COOLDOWN_SECONDS = 60

export default function SmsRegisterForm({
  onRequestCode,
  onRegister,
  onClearError,
  isSubmitting,
  error,
  defaultLocale,
}: SmsRegisterFormProps) {
  const { t } = useI18n()
  const [mobile, setMobile] = useState('')
  const [code, setCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [preferredLanguage, setPreferredLanguage] = useState<Locale>(defaultLocale)
  const [localError, setLocalError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [codeCountdown, setCodeCountdown] = useState(0)
  const [isRequestingCode, setIsRequestingCode] = useState(false)

  const activeError = localError || error || null

  const normalizeMobileInput = (value: string): string | null => {
    let sanitized = value.trim().replace(/\s+/g, '')
    if (!sanitized) {
      return null
    }

    if (sanitized.startsWith('00')) {
      sanitized = sanitized.slice(2)
    }

    if (sanitized.startsWith('+')) {
      sanitized = sanitized.slice(1)
    }

    if (!/^\d+$/.test(sanitized)) {
      return null
    }

    if (sanitized.length === 11 && sanitized.startsWith('1')) {
      sanitized = `86${sanitized}`
    }

    if (sanitized.startsWith('86') && sanitized.length === 13) {
      return `+${sanitized}`
    }

    return null
  }

  useEffect(() => {
    if (!error || !onClearError) {
      return
    }
    const timer = setTimeout(() => onClearError(), 5000)
    return () => clearTimeout(timer)
  }, [error, onClearError])

  useEffect(() => {
    if (codeCountdown <= 0) {
      return
    }
    const timer = setInterval(() => {
      setCodeCountdown(prev => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [codeCountdown])

  const handleChange =
    (setter: (value: string) => void) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      if (activeError && onClearError) {
        onClearError()
      }
      if (localError) {
        setLocalError(null)
      }
      setter(event.target.value)
    }

  const handleSendCode = async () => {
    const trimmedMobile = mobile.trim()
    const normalized = normalizeMobileInput(trimmedMobile)
    if (!normalized) {
      setLocalError(t('auth.smsInvalidPhone'))
      return
    }

    setLocalError(null)
    setStatusMessage(null)
    setIsRequestingCode(true)
    try {
      setMobile(normalized)
      await onRequestCode(normalized)
      setStatusMessage(t('auth.smsCodeSent'))
      setCodeCountdown(RESEND_COOLDOWN_SECONDS)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : t('auth.smsCodeFailed'))
    } finally {
      setIsRequestingCode(false)
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLocalError(null)
    setStatusMessage(null)

    if (password !== confirmPassword) {
      setLocalError(t('register.passwordMismatch'))
      return
    }

    const normalizedMobile = normalizeMobileInput(mobile)
    if (!normalizedMobile) {
      setLocalError(t('auth.smsInvalidPhone'))
      return
    }

    if (!code.trim()) {
      setLocalError(t('auth.smsMissingFields'))
      return
    }

    if (password.length < 8) {
      setLocalError(t('auth.passwordTooShort'))
      return
    }

    try {
      await onRegister({
        mobile: normalizedMobile,
        code: code.trim(),
        password,
        username: username.trim() || undefined,
        preferred_language: preferredLanguage,
      })
      setStatusMessage(t('auth.smsRegisterSuccess'))
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : t('auth.smsRegisterFailed'))
    }
  }

  const isCodeButtonDisabled =
    isRequestingCode || codeCountdown > 0 || !normalizeMobileInput(mobile)

  const codeButtonLabel = codeCountdown > 0
    ? t('auth.smsResendIn', { seconds: codeCountdown })
    : t('auth.smsSendCode')

  const canSubmit = useMemo(() => {
    return Boolean(
      normalizeMobileInput(mobile) &&
      code.trim() &&
      password &&
      confirmPassword &&
      !isSubmitting
    )
  }, [mobile, code, password, confirmPassword, isSubmitting])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-center">
            {t('auth.smsRegisterTitle')}
          </CardTitle>
          <p className="text-sm text-muted-foreground text-center">
            {t('auth.smsRegisterDescription')}
          </p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <Input
              type="tel"
              inputMode="tel"
              placeholder={t('auth.phonePlaceholder')}
              value={mobile}
              onChange={handleChange(setMobile)}
              disabled={isSubmitting}
              required
            />
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder={t('auth.smsCodePlaceholder')}
                value={code}
                onChange={handleChange(setCode)}
                disabled={isSubmitting}
                required
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleSendCode}
                disabled={isCodeButtonDisabled}
              >
                {isRequestingCode ? t('common.statuses.loading') : codeButtonLabel}
              </Button>
            </div>
            <Input
              type="text"
              placeholder={t('auth.usernamePlaceholder')}
              value={username}
              onChange={handleChange(setUsername)}
              disabled={isSubmitting}
            />
            <Input
              type="password"
              placeholder={t('auth.passwordPlaceholder')}
              value={password}
              onChange={handleChange(setPassword)}
              disabled={isSubmitting}
              required
            />
            <Input
              type="password"
              placeholder={t('auth.confirmPasswordPlaceholder')}
              value={confirmPassword}
              onChange={handleChange(setConfirmPassword)}
              disabled={isSubmitting}
              required
            />

            <div>
              <label className="block text-sm font-medium mb-1">
                {t('chat.localeToggleLabel')}
              </label>
              <select
                className="w-full px-3 py-2 border rounded-md"
                value={preferredLanguage}
                onChange={handleChange((value) => setPreferredLanguage(value as Locale))}
                disabled={isSubmitting}
              >
                {supportedLocales.map((loc) => (
                  <option key={loc} value={loc}>
                    {getLocaleName(loc)}
                  </option>
                ))}
              </select>
            </div>

            <p className="text-xs text-muted-foreground">
              {t('auth.smsAutoCountryHint')}
            </p>

            {activeError && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertTriangle className="h-4 w-4" />
                <span>{activeError}</span>
              </div>
            )}

            {statusMessage && (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle2 className="h-4 w-4" />
                <span>{statusMessage}</span>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={!canSubmit}>
              {isSubmitting ? t('auth.registering') : t('common.buttons.register')}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              <Link href="/login" className="text-primary hover:underline">
                {t('auth.haveAccount')}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
