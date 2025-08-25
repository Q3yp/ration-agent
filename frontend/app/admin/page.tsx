'use client'

import ProtectedRoute from '@/components/auth/ProtectedRoute'
import UserManagement from '@/components/admin/UserManagement'

export default function AdminPage() {
  return (
    <ProtectedRoute adminOnly={true}>
      <UserManagement />
    </ProtectedRoute>
  )
}