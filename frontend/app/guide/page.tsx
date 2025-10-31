'use client'

import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import UserGuide from '@/components/UserGuide'
import Link from 'next/link'
import ProtectedRoute from '@/components/auth/ProtectedRoute'

export default function GuidePage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-br from-background to-muted">
        <header className="sticky top-0 z-10 bg-background/80 backdrop-blur-sm border-b">
          <div className="container mx-auto px-6 py-4">
            <Link href="/chat">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                返回对话
              </Button>
            </Link>
          </div>
        </header>

        <UserGuide />
      </div>
    </ProtectedRoute>
  )
}
