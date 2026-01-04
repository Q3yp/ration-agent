'use client'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import FeedbaseManager from '@/components/feedbase/FeedbaseManager'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import { useAuthContext } from '@/contexts/AuthContext'
import { useI18n } from '@/contexts/I18nContext'
import { Badge } from '@/components/ui/badge'
import BackToChatButton from '@/components/layout/BackToChatButton'

export default function FeedbasesPage() {
  const { user, logout } = useAuthContext()
  const { t } = useI18n()
  const tierBadgeText = user?.tier === 'paid'
    ? t('chat.tierBadges.paid')
    : user?.tier === 'free'
      ? t('chat.tierBadges.free')
      : null

  return (
    <ProtectedRoute>
      <main className="h-screen overflow-hidden bg-gradient-to-br from-background to-muted">
        <div className="h-full flex flex-col overflow-hidden">
          {/* Header */}
          <header className="py-2 sm:py-4 px-3 sm:px-6 border-b flex-shrink-0">
            <div className="flex justify-between items-center gap-2">
              <div className="flex items-center gap-2 sm:gap-4 min-w-0">
                <BackToChatButton label={t('feedbases.back')} />
                <h1 className="text-base sm:text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent truncate">
                  {t('feedbases.title')}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden md:inline text-sm text-muted-foreground truncate">
                  {user?.username ? t('common.welcomeUser', { name: user.username }) : t('common.welcomeGeneric')}
                </span>
                {tierBadgeText && (
                  <Badge
                    variant={user?.tier === 'paid' ? 'default' : 'secondary'}
                    className="text-[10px] uppercase"
                    title={t('chat.tierLabel')}
                  >
                    {tierBadgeText}
                  </Badge>
                )}
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
