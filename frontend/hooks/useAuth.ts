'use client'

import { useState, useEffect } from 'react'
import { httpClient } from '@/utils/httpClient'

type SmsPurpose = 'register' | 'login' | 'bind'

interface User {
  id: string
  email?: string | null
  username: string
  full_name?: string
  role: string
  is_superuser: boolean
  preferred_language: 'zh-CN' | 'en-US'
  phone_number?: string | null
  tier: 'free' | 'paid'
}

interface SmsRegisterPayload {
  mobile: string
  code: string
  password: string
  username?: string
  email?: string
  full_name?: string
  preferred_language?: 'zh-CN' | 'en-US'
}

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  login: (identifier: string, password: string) => Promise<void>
  loginWithGoogleIdToken: (idToken: string) => Promise<void>
  registerWithSms: (payload: SmsRegisterPayload) => Promise<void>
  requestSmsCode: (mobile: string, purpose?: SmsPurpose) => Promise<{ message: string; expires_in: number }>
  logout: () => void
  clearError: () => void
}

export type AuthContextType = AuthState & AuthActions

export const useAuth = (): AuthContextType => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
    error: null
  })

  // Check for existing token on mount
  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      // Verify token and get user info
      verifyToken(token)
    } else {
      setAuthState(prev => ({ ...prev, isLoading: false }))
    }
  }, [])

  const verifyToken = async (token: string) => {
    try {
      const user = await httpClient.getJson('/auth/users/me')
      setAuthState({
        user,
        token,
        isLoading: false,
        error: null
      })
    } catch (error) {
      // Token invalid, remove it
      localStorage.removeItem('auth_token')
      setAuthState({
        user: null,
        token: null,
        isLoading: false,
        error: null
      })
    }
  }

  const login = async (identifier: string, password: string) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }))
    
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password })
      })

      if (response.ok) {
        const data = await response.json()
        const token = data.access_token
        
        // Store token
        localStorage.setItem('auth_token', token)
        
        // Get user info
        await verifyToken(token)
      } else {
        const error = await response.json()
        setAuthState(prev => ({
          ...prev,
          isLoading: false,
          error: error.detail || 'Login failed'
        }))
      }
    } catch (error) {
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: 'Network error during login'
      }))
    }
  }

  const requestSmsCode = async (
    mobile: string,
    purpose: SmsPurpose = 'register'
  ): Promise<{ message: string; expires_in: number }> => {
    try {
      const response = await fetch('/auth/sms/code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mobile, purpose }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to send SMS code')
      }
      return data
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : 'Failed to send SMS code')
    }
  }

  const registerWithSms = async (payload: SmsRegisterPayload) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }))
    try {
      const response = await fetch('/auth/sms/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || 'SMS registration failed')
      }

      const token = data.access_token as string | undefined
      if (!token) {
        throw new Error('Registration succeeded but no token was returned')
      }

      localStorage.setItem('auth_token', token)
      await verifyToken(token)
    } catch (error) {
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'SMS registration failed',
      }))
      throw error
    }
  }

  const loginWithGoogleIdToken = async (idToken: string) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }))

    try {
      const response = await fetch('/auth/google/id-token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id_token: idToken })
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || 'Google login failed')
      }

      const data = await response.json()
      const token = data.access_token

      localStorage.setItem('auth_token', token)
      await verifyToken(token)
    } catch (error) {
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Google login failed'
      }))
      throw error
    }
  }

  const logout = () => {
    localStorage.removeItem('auth_token')
    setAuthState({
      user: null,
      token: null,
      isLoading: false,
      error: null
    })
  }

  const clearError = () => {
    setAuthState(prev => ({ ...prev, error: null }))
  }

  return {
    ...authState,
    login,
    loginWithGoogleIdToken,
    registerWithSms,
    requestSmsCode,
    logout,
    clearError
  }
}
