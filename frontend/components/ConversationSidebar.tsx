'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, MessageCircle, Loader2, TrashIcon } from 'lucide-react'
import { Session, AnimalType } from '@/types/chat'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { httpClient } from '@/utils/httpClient'
import { AnimalTypeSelector } from './AnimalTypeSelector'
import { TokenUsage } from './TokenUsage'

interface ConversationSidebarProps {
  currentSessionId: string | null
  onSessionSelect: (sessionId: string) => void
  onNewSession: (sessionId: string) => void
  sessionTitles: Record<string, string>
  sessionTokenUsage: Record<string, import('@/types/chat').TokenUsage>
}

export default function ConversationSidebar({
  currentSessionId,
  onSessionSelect,
  onNewSession,
  sessionTitles,
  sessionTokenUsage,
}: ConversationSidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAnimalTypeSelector, setShowAnimalTypeSelector] = useState(false)

  // Update session titles when sessionTitles prop changes
  useEffect(() => {
    setSessions(prev => prev.map(session => ({
      ...session,
      title: sessionTitles[session.session_id] || session.title
    })))
  }, [sessionTitles])

  // Update session token usage when sessionTokenUsage prop changes
  useEffect(() => {
    setSessions(prev => prev.map(session => ({
      ...session,
      token_usage: sessionTokenUsage[session.session_id] || session.token_usage
    })))
  }, [sessionTokenUsage])


  const fetchSessions = async () => {
    try {
      setIsLoading(true)
      const data = await httpClient.getJson(`/sessions/list`)
      const sessions = data.active_sessions || []
      setSessions(sessions)
      
      // If no sessions exist and no current session, show selector
      if (sessions.length === 0 && !currentSessionId) {
        setShowAnimalTypeSelector(true)
      }
    } catch (error) {
      console.error('Error fetching sessions:', error)
      alert('获取对话列表失败，请刷新页面重试')
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewSessionClick = () => {
    setShowAnimalTypeSelector(true)
  }

  const createNewSession = async (animalType: AnimalType) => {
    try {
      const response = await httpClient.postJson(`/sessions/create`, {
        animal_type: animalType
      })

      // Backend generates session_id, use it from response
      const newSession: Session = {
        session_id: response.session_id,
        title: '新对话',
        created_at: new Date().toISOString(),
        animal_type: response.animal_type
      }
      setSessions(prev => [newSession, ...prev])

      setShowAnimalTypeSelector(false)
      onSessionSelect(response.session_id)
      onNewSession(response.session_id)
    } catch (error) {
      console.error('Error creating session:', error)
      alert('创建新对话失败，请重试')
    }
  }

  const deleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation()
    
    if (!confirm('您确定要删除这个对话吗？')) {
      return
    }

    try {
      await httpClient.deleteJson(`/sessions/${sessionId}`)
      
      // Remove session from local state instead of refetching all sessions
      setSessions(prev => prev.filter(session => session.session_id !== sessionId))
      
      // If we deleted the current session, show the selector
      if (sessionId === currentSessionId) {
        setShowAnimalTypeSelector(true)
      }
    } catch (error) {
      console.error('Error deleting session:', error)
      alert('删除对话失败，请重试')
    }
  }

  const deleteAllSessions = async () => {
    if (!confirm('您确定要删除所有对话吗？这个操作不可恢复。')) {
      return
    }

    try {
      await httpClient.deleteJson(`/sessions/delete-all`)
      
      // Clear all sessions from local state
      setSessions([])

      // Show animal type selector for new session
      setShowAnimalTypeSelector(true)
    } catch (error) {
      console.error('Error deleting all sessions:', error)
      alert('删除所有对话失败，请重试')
    }
  }

  const formatTimestamp = (session: Session) => {
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

  const getAnimalTypeLabel = (animalType?: string) => {
    const labels: Record<string, string> = {
      'dairy_cow': '奶牛',
      'beef_cow': '肉牛',
      'cat': '猫',
      'dog': '狗'
    }
    return labels[animalType || 'dairy_cow'] || '奶牛'
  }

  const getAnimalTypeEmoji = (animalType?: string) => {
    const emojis: Record<string, string> = {
      'dairy_cow': '🐄',
      'beef_cow': '🐂',
      'cat': '🐱',
      'dog': '🐶'
    }
    return emojis[animalType || 'dairy_cow'] || '🐄'
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
    <>
      {showAnimalTypeSelector && (
        <AnimalTypeSelector
          onSelect={createNewSession}
          onCancel={() => setShowAnimalTypeSelector(false)}
        />
      )}

      <div className="w-80 bg-muted/30 border-r flex flex-col">
        {/* Header */}
        <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">对话列表</h2>
          <div className="flex items-center gap-1">
            {sessions.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={deleteAllSessions}
                title="删除所有对话"
                className="h-8 w-8 text-destructive hover:text-destructive"
              >
                <TrashIcon className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNewSessionClick}
              title="新建对话"
              className="h-8 w-8"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>


      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-4">
        {sessions.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground mb-3">还没有对话</p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNewSessionClick}
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
                  <div className="flex flex-col">
                    <div className="flex items-start justify-between mb-1">
                      <div className="flex items-start space-x-3 flex-1 min-w-0">
                        <MessageCircle className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">
                            {session.title || 'New Conversation'}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {formatTimestamp(session)}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => deleteSession(session.session_id, e)}
                        className="opacity-0 group-hover:opacity-100 h-6 w-6 text-destructive hover:text-destructive flex-shrink-0"
                        title="删除对话"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                    <div className="flex items-center justify-between pl-7">
                      <div className="flex items-center gap-2">
                        <span className="text-base">
                          {getAnimalTypeEmoji(session.animal_type)}
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
                          {getAnimalTypeLabel(session.animal_type)}
                        </span>
                      </div>
                      <TokenUsage tokenUsage={session.token_usage} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
        </div>
      </div>
    </>
  )
}