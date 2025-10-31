'use client'

import { useState } from 'react'
import { MessageCircle, User, LogOut, Database, BookOpen } from 'lucide-react'
import ChatInterface from '@/components/ChatInterface'
import ConversationSidebar from '@/components/ConversationSidebar'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuthContext } from '@/contexts/AuthContext'
import Link from 'next/link'

export default function Home() {
  const { user, logout } = useAuthContext()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chatKey, setChatKey] = useState(0) // Force ChatInterface re-render when session changes
  const [sessionTitles, setSessionTitles] = useState<Record<string, string>>({})
  const [sessionTokenUsage, setSessionTokenUsage] = useState<Record<string, import('@/types/chat').TokenUsage>>({})

  const handleSessionSelect = (newSessionId: string) => {
    setSessionId(newSessionId)
    setChatKey(prev => prev + 1) // Force ChatInterface to re-render with new session
  }

  const handleNewSession = (newSessionId: string) => {
    setSessionId(newSessionId)
    setChatKey(prev => prev + 1) // Force ChatInterface to re-render for new session
  }

  const handleTitleUpdate = (sessionId: string, title: string) => {
    setSessionTitles(prev => ({
      ...prev,
      [sessionId]: title
    }))
  }

  const handleTokenUsageUpdate = (sessionId: string, tokenUsage: import('@/types/chat').TokenUsage) => {
    setSessionTokenUsage(prev => ({
      ...prev,
      [sessionId]: tokenUsage
    }))
  }

  return (
    <ProtectedRoute>
      <main className="h-screen bg-gradient-to-br from-background to-muted">
        <div className="h-full flex">
          {/* Sidebar */}
          <ConversationSidebar
            currentSessionId={sessionId}
            onSessionSelect={handleSessionSelect}
            onNewSession={handleNewSession}
            sessionTitles={sessionTitles}
            sessionTokenUsage={sessionTokenUsage}
          />
          
          {/* Main content */}
          <div className="flex-1 flex flex-col">
            <header className="py-4 px-6 border-b">
              <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                  辉途智能配方助手
                </h1>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    欢迎，{user?.username}
                  </span>
                  <Link href="/guide">
                    <Button variant="outline" size="sm">
                      <BookOpen className="h-4 w-4 mr-1" />
                      使用指南
                    </Button>
                  </Link>
                  <Link href="/feedbases">
                    <Button variant="outline" size="sm">
                      <Database className="h-4 w-4 mr-1" />
                      饲料库管理
                    </Button>
                  </Link>
                  {user?.is_superuser && (
                    <Link href="/admin">
                      <Button variant="outline" size="sm">
                        <User className="h-4 w-4 mr-1" />
                        用户管理
                      </Button>
                    </Link>
                  )}
                  <Button variant="outline" size="sm" onClick={logout}>
                    <LogOut className="h-4 w-4 mr-1" />
                    退出登录
                  </Button>
                </div>
              </div>
            </header>
          
          <div className="flex-1 p-6 min-h-0">
            {sessionId ? (
              <div className="h-full max-h-full">
                <ChatInterface
                  key={chatKey}
                  sessionId={sessionId}
                  onTitleUpdate={handleTitleUpdate}
                  onTokenUsageUpdate={handleTokenUsageUpdate}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <Card className="w-96">
                  <CardContent className="p-6 text-center">
                    <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground mb-3">请选择或创建一个对话</p>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
      </main>
    </ProtectedRoute>
  )
}