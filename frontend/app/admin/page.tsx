'use client'

import ProtectedRoute from '@/components/auth/ProtectedRoute'
import UserManagement from '@/components/admin/UserManagement'
import FeedbackManagement from '@/components/admin/FeedbackManagement'
import BackToChatButton from '@/components/BackToChatButton'
import { useI18n } from '@/contexts/I18nContext'
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

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
        <div className="py-4 container mx-auto px-6">
          <Tabs defaultValue="users" className="w-full">
            <TabsList className="grid w-full grid-cols-2 max-w-[400px] mb-6">
              <TabsTrigger value="users">{t('admin.userManagement')}</TabsTrigger>
              <TabsTrigger value="feedbacks">{t('admin.feedbackManagement')}</TabsTrigger>
            </TabsList>
            <TabsContent value="users">
              <UserManagement />
            </TabsContent>
            <TabsContent value="feedbacks">
              <FeedbackManagement />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </ProtectedRoute>
  )
}
