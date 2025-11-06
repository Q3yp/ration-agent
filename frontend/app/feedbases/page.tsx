'use client'

import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import FeedbaseManager from '@/components/FeedbaseManager'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import { useAuthContext } from '@/contexts/AuthContext'
import Link from 'next/link'
import { useI18n } from '@/contexts/I18nContext'

export default function FeedbasesPage() {
  const { user, logout } = useAuthContext()
  const { t } = useI18n()

  return (
    <ProtectedRoute>
      <main className="h-screen bg-gradient-to-br from-background to-muted">
        <div className="h-full flex flex-col">
          {/* Header */}
          <header className="py-4 px-6 border-b">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <Link href="/chat">
                  <Button variant="outline" size="sm">
                    <ArrowLeft className="h-4 w-4 mr-1" />
                    {t('feedbases.back')}
                  </Button>
                </Link>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                  {t('feedbases.title')}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  {user?.username ? t('common.welcomeUser', { name: user.username }) : t('common.welcomeGeneric')}
                </span>
                <Button variant="outline" size="sm" onClick={logout}>
                  {t('common.buttons.logout')}
                </Button>
              </div>
            </div>
          </header>
          
          {/* Main content */}
          <div className="flex-1 p-6 min-h-0">
            <Card className="h-full">
              <CardContent className="p-6 h-full">
                <FeedbaseManager />
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </ProtectedRoute>
  )
}
