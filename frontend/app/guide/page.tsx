'use client'

import UserGuide from '@/components/UserGuide'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import { useI18n } from '@/contexts/I18nContext'
import BackToChatButton from '@/components/BackToChatButton'

export default function GuidePage() {
  const { t } = useI18n()
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-br from-background to-muted">
        <header className="sticky top-0 z-10 bg-background/80 backdrop-blur-sm border-b">
          <div className="container mx-auto px-6 py-4">
            <BackToChatButton label={t('guide.back')} />
          </div>
        </header>

        <UserGuide />
      </div>
    </ProtectedRoute>
  )
}
