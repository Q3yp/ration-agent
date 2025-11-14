'use client'

import ProtectedRoute from '@/components/auth/ProtectedRoute'
import UserManagement from '@/components/admin/UserManagement'
import BackToChatButton from '@/components/BackToChatButton'
import { useI18n } from '@/contexts/I18nContext'

export default function AdminPage() {
  const { t } = useI18n()

  return (
    <ProtectedRoute adminOnly={true}>
      <div className="min-h-screen bg-gradient-to-br from-background to-muted">
        <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
          <div className="px-4 sm:px-6 py-3">
            <BackToChatButton label={t('admin.back')} />
          </div>
        </header>
        <div className="py-4">
          <UserManagement />
        </div>
      </div>
    </ProtectedRoute>
  )
}
