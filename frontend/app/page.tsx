'use client'

import { useState, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Loader2, AlertTriangle } from 'lucide-react'
import ChatInterface from '@/components/ChatInterface'
import ConversationSidebar from '@/components/ConversationSidebar'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [isCreatingSession, setIsCreatingSession] = useState(true)
  const [chatKey, setChatKey] = useState(0) // Force ChatInterface re-render when session changes

  useEffect(() => {
    const createSession = async () => {
      const generatedSessionId = uuidv4()
      
      try {
        const response = await fetch('http://localhost:8000/sessions/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ session_id: generatedSessionId }),
        })
        
        if (!response.ok) {
          throw new Error(`Failed to create session: ${response.statusText}`)
        }
        
        const data = await response.json()
        setSessionId(data.session_id)
        setSessionError(null)
      } catch (error) {
        console.error('Session creation error:', error)
        setSessionError(error instanceof Error ? error.message : 'Failed to create session')
      } finally {
        setIsCreatingSession(false)
      }
    }
    
    createSession()
  }, [])

  const handleSessionSelect = (newSessionId: string) => {
    setSessionId(newSessionId)
    setChatKey(prev => prev + 1) // Force ChatInterface to re-render with new session
  }

  const handleNewSession = () => {
    setChatKey(prev => prev + 1) // Force ChatInterface to re-render for new session
  }

  return (
    <main className="h-screen bg-gradient-to-br from-background to-muted">
      <div className="h-full flex">
        {/* Sidebar */}
        <ConversationSidebar 
          currentSessionId={sessionId}
          onSessionSelect={handleSessionSelect}
          onNewSession={handleNewSession}
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
            {isCreatingSession ? (
              <div className="flex items-center justify-center h-full">
                <Card className="w-96">
                  <CardContent className="p-6 text-center">
                    <Loader2 className="animate-spin h-8 w-8 mx-auto mb-4 text-primary" />
                    <p className="text-muted-foreground">正在创建会话...</p>
                  </CardContent>
                </Card>
              </div>
            ) : sessionError ? (
              <div className="flex items-center justify-center h-full">
                <Card className="w-96">
                  <CardContent className="p-6 text-center">
                    <AlertTriangle className="h-8 w-8 mx-auto mb-4 text-destructive" />
                    <p className="text-destructive mb-4">{sessionError}</p>
                    <Button 
                      variant="destructive"
                      onClick={() => window.location.reload()}
                    >
                      重试
                    </Button>
                  </CardContent>
                </Card>
              </div>
            ) : sessionId ? (
              <div className="h-full max-h-full">
                <ChatInterface 
                  key={chatKey} 
                  sessionId={sessionId} 
                />
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </main>
  )
}