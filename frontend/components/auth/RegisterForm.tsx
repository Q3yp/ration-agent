'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { AlertTriangle } from 'lucide-react'
import Link from 'next/link'
import { supportedLocales, getLocaleName, Locale } from '@/lib/i18n/locales'
import { useI18n } from '@/contexts/I18nContext'

interface RegisterFormProps {
  onSuccess?: () => void
}

export default function RegisterForm({ onSuccess }: RegisterFormProps) {
  const { t, locale } = useI18n()
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    preferred_language: locale as Locale,
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleChange = (key: string, value: string) => {
    setFormData(prev => ({ ...prev, [key]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    if (formData.password !== formData.confirmPassword) {
      setError(t('register.passwordMismatch'))
      return
    }

    setIsSubmitting(true)

    try {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: formData.email,
          username: formData.username,
          password: formData.password,
          preferred_language: formData.preferred_language,
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Registration failed')
      }

      setSuccess(t('register.success'))
      setFormData(prev => ({ ...prev, password: '', confirmPassword: '' }))
      onSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-center">
            {t('auth.registerTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <Input
              type="email"
              placeholder={t('auth.emailPlaceholder')}
              value={formData.email}
              onChange={(e) => handleChange('email', e.target.value)}
              disabled={isSubmitting}
              required
            />
            <Input
              type="text"
              placeholder={t('auth.usernamePlaceholder')}
              value={formData.username}
              onChange={(e) => handleChange('username', e.target.value)}
              disabled={isSubmitting}
              required
            />
            <Input
              type="password"
              placeholder={t('auth.passwordPlaceholder')}
              value={formData.password}
              onChange={(e) => handleChange('password', e.target.value)}
              disabled={isSubmitting}
              required
            />
            <Input
              type="password"
              placeholder={t('auth.confirmPasswordPlaceholder')}
              value={formData.confirmPassword}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              disabled={isSubmitting}
              required
            />
            <div>
              <label className="block text-sm font-medium mb-1">
                {t('chat.localeToggleLabel')}
              </label>
              <select
                className="w-full px-3 py-2 border rounded-md"
                value={formData.preferred_language}
                onChange={(e) => handleChange('preferred_language', e.target.value)}
                disabled={isSubmitting}
              >
                {supportedLocales.map((loc) => (
                  <option key={loc} value={loc}>
                    {getLocaleName(loc)}
                  </option>
                ))}
              </select>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertTriangle className="h-4 w-4" />
                {error}
              </div>
            )}

            {success && (
              <div className="text-sm text-green-600">
                {success}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
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
