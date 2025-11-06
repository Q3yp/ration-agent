'use client'

import { useEffect } from 'react'
import { useAuthContext } from '@/contexts/AuthContext'
import LoginForm from './LoginForm'
import { useI18n } from '@/contexts/I18nContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  adminOnly?: boolean
}

export default function ProtectedRoute({ children, adminOnly = false }: ProtectedRouteProps) {
  const { user, token, isLoading, login, error, clearError } = useAuthContext()
  const { t } = useI18n()

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => clearError(), 5000)
      return () => clearTimeout(timer)
    }
  }, [error, clearError])

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
          <p className="mt-2">{t('common.statuses.loading')}</p>
        </div>
      </div>
    )
  }

  // Show login form if not authenticated
  if (!user || !token) {
    return (
      <LoginForm 
        onLogin={login}
        isLoading={isLoading}
        error={error || undefined}
      />
    )
  }

  // Check admin permissions
  if (adminOnly && !user.is_superuser) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-2">{t('protectedRoute.deniedTitle')}</h1>
          <p className="text-gray-600">{t('protectedRoute.deniedDescription')}</p>
        </div>
      </div>
    )
  }

  // User is authenticated and has required permissions
  return <>{children}</>
}
