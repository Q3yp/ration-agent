'use client'

import { createContext, useContext, useEffect } from 'react'
import { useAuth, AuthContextType } from '@/hooks/useAuth'
import { useI18n } from './I18nContext'

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const { setLocale } = useI18n()

  useEffect(() => {
    if (auth.user?.preferred_language) {
      void setLocale(auth.user.preferred_language, { notifyServer: false })
    }
  }, [auth.user?.preferred_language, setLocale])
  
  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthContext(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider')
  }
  return context
}
