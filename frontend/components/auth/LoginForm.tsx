'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle } from 'lucide-react'
import { useI18n } from '@/contexts/I18nContext'
import { useAuthContext } from '@/contexts/AuthContext'

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (options: {
            client_id: string
            callback: (response: { credential?: string }) => void
            ux_mode?: 'popup' | 'redirect'
            auto_select?: boolean
          }) => void
          renderButton: (
            element: HTMLElement,
            options: {
              type?: 'standard' | 'icon'
              theme?: 'outline' | 'filled_blue' | 'filled_black'
              size?: 'small' | 'medium' | 'large'
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
              shape?: 'rectangular' | 'pill' | 'circle' | 'square'
              width?: string | number
            }
          ) => void
          prompt: () => void
        }
      }
    }
  }
}

interface LoginFormProps {
  onLogin: (identifier: string, password: string) => Promise<void>
  isLoading?: boolean
  error?: string
}

export default function LoginForm({ onLogin, isLoading, error }: LoginFormProps) {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)
  const [googleError, setGoogleError] = useState<string | null>(null)
  const buttonRef = useRef<HTMLDivElement | null>(null)
  const { t } = useI18n()
  const { loginWithGoogleIdToken } = useAuthContext()
  const [googleClientId, setGoogleClientId] = useState('')

  // Fetch Google Client ID from server at runtime (not baked in at build time)
  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => setGoogleClientId(data.googleClientId || ''))
      .catch(() => setGoogleClientId(''))
  }, [])

  const clearLocalError = () => {
    if (localError) {
      setLocalError(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedIdentifier = identifier.trim()
    if (!trimmedIdentifier) {
      setLocalError(t('auth.accountRequired'))
      return
    }
    if (!password) {
      setLocalError(t('auth.passwordRequired'))
      return
    }

    await onLogin(trimmedIdentifier, password)
  }

  const handleGoogleCredential = useCallback(
    async (response: { credential?: string }) => {
      if (!response.credential) {
        setGoogleError(t('auth.googleLoginError'))
        return
      }

      setIsGoogleLoading(true)
      try {
        await loginWithGoogleIdToken(response.credential)
        setGoogleError(null)
      } catch (err) {
        console.error(err)
        setGoogleError(t('auth.googleLoginError'))
      } finally {
        setIsGoogleLoading(false)
      }
    },
    [loginWithGoogleIdToken, t]
  )

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    if (!googleClientId) {
      setGoogleError(t('auth.googleMissingClientId'))
      return
    }

    let isMounted = true

    const initGoogle = () => {
      const googleAccounts = window.google?.accounts?.id
      if (!googleAccounts) {
        if (isMounted) {
          setGoogleError(t('auth.googleInitError'))
        }
        return
      }

      googleAccounts.initialize({
        client_id: googleClientId,
        callback: handleGoogleCredential,
        ux_mode: 'popup',
      })

      if (buttonRef.current) {
        buttonRef.current.innerHTML = ''
        googleAccounts.renderButton(buttonRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          width: '100%',
        })
      }

      googleAccounts.prompt()
      setGoogleError(null)
    }

    if (window.google?.accounts?.id) {
      initGoogle()
      return () => {
        isMounted = false
      }
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => initGoogle()
    script.onerror = () => {
      if (isMounted) {
        setGoogleError(t('auth.googleInitError'))
      }
    }
    document.head.appendChild(script)

    return () => {
      isMounted = false
      script.onload = null
      script.onerror = null
    }
  }, [googleClientId, handleGoogleCredential, t])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-center">
            {t('auth.loginTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Input
                type="text"
                placeholder={t('auth.accountPlaceholder')}
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value)
                  clearLocalError()
                }}
                disabled={isLoading}
                required
              />
            </div>
            
            <div>
              <Input
                type="password"
                placeholder={t('auth.passwordPlaceholder')}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  clearLocalError()
                }}
                disabled={isLoading}
                required
              />
            </div>
            
            {(localError || error) && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertTriangle size={16} />
                {localError || error}
              </div>
            )}
            
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || !identifier || !password}
            >
              {isLoading ? t('auth.loggingIn') : t('common.buttons.login')}
            </Button>

            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white px-2 text-muted-foreground">
                  {t('auth.or')}
                </span>
              </div>
            </div>

            <div className="w-full flex flex-col items-center gap-2">
              <div className="w-full flex justify-center" ref={buttonRef} />
              {isGoogleLoading && (
                <div className="text-sm text-muted-foreground">
                  {t('auth.loggingIn')}
                </div>
              )}
            </div>

            {googleError && (
              <div className="text-sm text-red-600 text-center">
                {googleError}
              </div>
            )}

            <p className="text-center text-sm text-muted-foreground">
              {t('auth.googleOnlyNote')}
            </p>

            <p className="text-center text-sm text-muted-foreground">
              <Link href="/register" className="text-primary hover:underline">
                {t('auth.registerLink')}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
