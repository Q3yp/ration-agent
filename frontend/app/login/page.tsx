'use client'

import LoginForm from '@/components/auth/LoginForm'
import { useAuthContext } from '@/contexts/AuthContext'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const { user, isLoading, login, error, clearError } = useAuthContext()
  const router = useRouter()

  // If already logged in, redirect to home
  useEffect(() => {
    if (user) {
      router.replace('/')
    }
  }, [user, router])

  // Auto-clear transient errors
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => clearError(), 5000)
      return () => clearTimeout(t)
    }
  }, [error, clearError])

  return (
    <LoginForm
      onLogin={login}
      isLoading={isLoading}
      error={error || undefined}
    />
  )
}
