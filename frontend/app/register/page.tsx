'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import SmsRegisterForm from '@/components/auth/SmsRegisterForm'
import { useAuthContext } from '@/contexts/AuthContext'
import { useI18n } from '@/contexts/I18nContext'

export default function RegisterPage() {
  const { user, isLoading, requestSmsCode, registerWithSms, error, clearError } = useAuthContext()
  const { locale } = useI18n()
  const router = useRouter()

  useEffect(() => {
    if (user) {
      router.replace('/chat')
    }
  }, [user, router])

  return (
    <SmsRegisterForm
      onRequestCode={(mobile) => requestSmsCode(mobile, 'register')}
      onRegister={registerWithSms}
      onClearError={clearError}
      isSubmitting={isLoading}
      error={error}
      defaultLocale={locale}
    />
  )
}
