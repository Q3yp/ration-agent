'use client'

import { useState } from 'react'
import { MessageCircle } from 'lucide-react'
import ChatInterface from '@/components/ChatInterface'
import ConversationSidebar from '@/components/ConversationSidebar'
import { Card, CardContent } from '@/components/ui/card'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chatKey, setChatKey] = useState(0) // Force ChatInterface re-render when session changes
  const [sessionTitles, setSessionTitles] = useState<Record<string, string>>({})

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

  return (
    <main className="h-screen bg-gradient-to-br from-background to-muted">
      <div className="h-full flex">
        {/* Sidebar */}
        <ConversationSidebar
          currentSessionId={sessionId}
          onSessionSelect={handleSessionSelect}
          onNewSession={handleNewSession}
          sessionTitles={sessionTitles}
        />
        
        {/* Main content */}
        <div className="flex-1 flex flex-col">
          <header className="py-4 px-6 border-b">
            <div className="text-center">
              <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent mb-1">
                辉途智能配方助手
              </h1>
            </div>
          </header>
          
          <div className="flex-1 p-6 min-h-0">
            {sessionId ? (
              <div className="h-full max-h-full">
                <ChatInterface
                  key={chatKey}
                  sessionId={sessionId}
                  onTitleUpdate={handleTitleUpdate}
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
  )
}