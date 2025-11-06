'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle } from 'lucide-react'
import Link from 'next/link'
import { useI18n } from '@/contexts/I18nContext'

interface LoginFormProps {
  onLogin: (email: string, password: string) => Promise<void>
  isLoading?: boolean
  error?: string
}

export default function LoginForm({ onLogin, isLoading, error }: LoginFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { t } = useI18n()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (email && password) {
      await onLogin(email, password)
    }
  }

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
                type="email"
                placeholder={t('auth.emailPlaceholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>
            
            <div>
              <Input
                type="password"
                placeholder={t('auth.passwordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>
            
            {error && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertTriangle size={16} />
                {error}
              </div>
            )}
            
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || !email || !password}
            >
              {isLoading ? t('auth.loggingIn') : t('common.buttons.login')}
            </Button>

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
