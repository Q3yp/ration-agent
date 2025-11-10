'use client'

import { useState, useEffect } from 'react'
import { httpClient } from '@/utils/httpClient'

interface User {
  id: string
  email: string
  username: string
  full_name?: string
  role: string
  is_superuser: boolean
  preferred_language: 'zh-CN' | 'en-US'
}

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  login: (email: string, password: string) => Promise<void>
  loginWithGoogleIdToken: (idToken: string) => Promise<void>
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

  const login = async (email: string, password: string) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }))
    
    try {
      const formData = new FormData()
      formData.append('username', email) // FastAPI-Users uses 'username' field
      formData.append('password', password)

      const response = await fetch('/auth/jwt/login', {
        method: 'POST',
        body: formData
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
    logout,
    clearError
  }
}
