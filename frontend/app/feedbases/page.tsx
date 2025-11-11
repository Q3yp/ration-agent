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
      <main className="h-screen overflow-hidden bg-gradient-to-br from-background to-muted">
        <div className="h-full flex flex-col overflow-hidden">
          {/* Header */}
          <header className="py-2 sm:py-4 px-3 sm:px-6 border-b flex-shrink-0">
            <div className="flex justify-between items-center gap-2">
              <div className="flex items-center gap-2 sm:gap-4 min-w-0">
                <Link href="/chat">
                  <Button variant="outline" size="sm" className="h-8 sm:h-9">
                    <ArrowLeft className="h-4 w-4 sm:mr-1" />
                    <span className="hidden sm:inline">{t('feedbases.back')}</span>
                  </Button>
                </Link>
                <h1 className="text-base sm:text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent truncate">
                  {t('feedbases.title')}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden md:inline text-sm text-muted-foreground truncate">
                  {user?.username ? t('common.welcomeUser', { name: user.username }) : t('common.welcomeGeneric')}
                </span>
                <Button variant="outline" size="sm" onClick={logout} className="h-8 sm:h-9">
                  <span className="hidden sm:inline">{t('common.buttons.logout')}</span>
                  <span className="sm:hidden text-xs">{t('common.buttons.logout')}</span>
                </Button>
              </div>
            </div>
          </header>

          {/* Main content */}
          <div className="flex-1 p-3 sm:p-6 min-h-0 overflow-hidden">
            <Card className="h-full overflow-hidden flex flex-col">
              <CardContent className="p-3 sm:p-6 h-full overflow-hidden flex flex-col">
                <FeedbaseManager />
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </ProtectedRoute>
  )
}
