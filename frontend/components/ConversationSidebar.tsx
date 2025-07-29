'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, MessageCircle, Loader2 } from 'lucide-react'
import { Session } from '@/types/chat'
import { v4 as uuidv4 } from 'uuid'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface ConversationSidebarProps {
  currentSessionId: string | null
  onSessionSelect: (sessionId: string) => void
  onNewSession: () => void
  endpoint?: string
}

export default function ConversationSidebar({ 
  currentSessionId, 
  onSessionSelect, 
  onNewSession,
  endpoint = 'http://localhost:8000'
}: ConversationSidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSessions = async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`${endpoint}/sessions/list`)
      if (!response.ok) {
        throw new Error(`Failed to fetch sessions: ${response.statusText}`)
      }
      const data = await response.json()
      setSessions(data.active_sessions || [])
      setError(null)
    } catch (error) {
      console.error('Error fetching sessions:', error)
      setError(error instanceof Error ? error.message : 'Failed to fetch sessions')
    } finally {
      setIsLoading(false)
    }
  }

  const createNewSession = async () => {
    const newSessionId = uuidv4()
    try {
      const response = await fetch(`${endpoint}/sessions/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: newSessionId }),
      })
      
      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`)
      }
      
      await fetchSessions()
      onSessionSelect(newSessionId)
      onNewSession()
    } catch (error) {
      console.error('Error creating session:', error)
      setError(error instanceof Error ? error.message : 'Failed to create session')
    }
  }

  const deleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation()
    
    if (!confirm('您确定要删除这个对话吗？')) {
      return
    }

    try {
      const response = await fetch(`${endpoint}/sessions/${sessionId}`, {
        method: 'DELETE',
      })
      
      if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.statusText}`)
      }
      
      await fetchSessions()
      
      // If we deleted the current session, create a new one
      if (sessionId === currentSessionId) {
        await createNewSession()
      }
    } catch (error) {
      console.error('Error deleting session:', error)
      setError(error instanceof Error ? error.message : 'Failed to delete session')
    }
  }

  const formatSessionTitle = (session: Session) => {
    const date = new Date(session.created_at)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffHours / 24)
    
    if (diffHours < 1) {
      return '刚刚'
    } else if (diffHours < 24) {
      return `${diffHours}小时前`
    } else if (diffDays === 1) {
      return '昨天'
    } else if (diffDays < 7) {
      return `${diffDays}天前`
    } else {
      return date.toLocaleDateString()
    }
  }

  useEffect(() => {
    fetchSessions()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) {
    return (
      <div className="w-80 bg-muted/30 border-r flex flex-col">
        <CardHeader className="pb-3">
          <h2 className="text-lg font-semibold">对话历史</h2>
        </CardHeader>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="animate-spin h-6 w-6 text-muted-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="w-80 bg-muted/30 border-r flex flex-col">
      {/* Header */}
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">对话列表</h2>
          <Button
            variant="ghost"
            size="icon"
            onClick={createNewSession}
            title="新建对话"
            className="h-8 w-8"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      {/* Error display */}
      {error && (
        <div className="px-4 pb-3">
          <Card className="bg-destructive/10 border-destructive/20">
            <CardContent className="p-3">
              <p className="text-sm text-destructive">{error}</p>
              <Button
                variant="link"
                size="sm"
                onClick={fetchSessions}
                className="text-xs p-0 h-auto text-destructive"
              >
                重试
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-4">
        {sessions.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground mb-3">还没有对话</p>
            <Button
              variant="outline"
              size="sm"
              onClick={createNewSession}
            >
              开始对话
            </Button>
          </div>
        ) : (
          <div className="space-y-2 pb-4">
            {sessions.map((session) => (
              <Card
                key={session.session_id}
                onClick={() => onSessionSelect(session.session_id)}
                className={cn(
                  "group cursor-pointer transition-all hover:shadow-sm",
                  session.session_id === currentSessionId
                    ? "bg-primary/10 border-primary/20 shadow-sm"
                    : "hover:bg-muted/50"
                )}
              >
                <CardContent className="p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      <MessageCircle className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">
                          {formatSessionTitle(session)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => deleteSession(session.session_id, e)}
                      className="opacity-0 group-hover:opacity-100 h-6 w-6 text-destructive hover:text-destructive"
                      title="删除对话"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}