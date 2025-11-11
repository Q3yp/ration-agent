'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, MessageCircle, Loader2, TrashIcon, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Session, AnimalType } from '@/types/chat'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { httpClient } from '@/utils/httpClient'
import { AnimalTypeSelector } from './AnimalTypeSelector'
import { TokenUsage } from './TokenUsage'
import { useI18n } from '@/contexts/I18nContext'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'

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
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [showAnimalTypeSelector, setShowAnimalTypeSelector] = useState(false)
  const { t, formatRelativeTime } = useI18n()

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
    } catch (error) {
      console.error('Error fetching sessions:', error)
      alert(t('errors.networkRetry'))
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
        title: t('chat.newConversation'),
        created_at: new Date().toISOString(),
        animal_type: response.animal_type
      }
      setSessions(prev => [newSession, ...prev])

      setShowAnimalTypeSelector(false)
      onSessionSelect(response.session_id)
      onNewSession(response.session_id)
    } catch (error) {
      console.error('Error creating session:', error)
      alert(t('errors.networkRetry'))
    }
  }

  const deleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation()

    if (!confirm(t('sidebar.deleteConfirm'))) {
      return
    }

    try {
      await httpClient.deleteJson(`/sessions/${sessionId}`)

      // Remove session from local state instead of refetching all sessions
      setSessions(prev => prev.filter(session => session.session_id !== sessionId))
    } catch (error) {
      console.error('Error deleting session:', error)
      alert(t('errors.networkRetry'))
    }
  }

  const deleteAllSessions = async () => {
    if (!confirm(t('sidebar.deleteAllConfirm'))) {
      return
    }

    try {
      await httpClient.deleteJson(`/sessions/delete-all`)

      // Clear all sessions from local state
      setSessions([])
    } catch (error) {
      console.error('Error deleting all sessions:', error)
      alert(t('errors.networkRetry'))
    }
  }

  const formatTimestamp = (session: Session) => {
    return formatRelativeTime(session.created_at)
  }

  const getAnimalTypeLabel = (animalType?: string) => {
    const labels: Record<string, string> = {
      'dairy_cow': t('animalTypes.dairy_cow'),
      'beef_cow': t('animalTypes.beef_cow'),
      'cat': t('animalTypes.cat'),
      'dog': t('animalTypes.dog')
    }
    return labels[animalType || 'dairy_cow'] || t('animalTypes.dairy_cow')
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
          <h2 className="text-lg font-semibold">{t('sidebar.title')}</h2>
        </CardHeader>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="animate-spin h-6 w-6 text-muted-foreground" />
        </div>
      </div>
    )
  }

  const handleSessionClick = (sessionId: string) => {
    onSessionSelect(sessionId)
    setIsDrawerOpen(false) // Close drawer on mobile after selecting session
  }

  // Sidebar content component (reused for desktop and mobile drawer)
  const sidebarContent = (
    <div className="h-full flex flex-col bg-muted/30">
      {/* Header */}
      <CardHeader className="pb-3 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t('sidebar.title')}</h2>
          {sessions.length > 0 && (
            <Button
              variant="ghost"
              size="icon"
              onClick={deleteAllSessions}
              title={t('sidebar.deleteAllConfirm')}
              className="h-8 w-8 text-destructive hover:text-destructive"
            >
              <TrashIcon className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Large new chat button */}
        <Button
          onClick={handleNewSessionClick}
          className="w-full h-10 flex items-center justify-center gap-2"
          size="default"
        >
          <Plus className="h-5 w-5" />
          <span className="font-medium">{t('sidebar.newChat')}</span>
        </Button>
      </CardHeader>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-4">
        {sessions.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground mb-3">{t('common.statuses.historyPrompt')}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNewSessionClick}
            >
              {t('sidebar.newChat')}
            </Button>
          </div>
        ) : (
          <div className="space-y-2 pb-4">
            {sessions.map((session) => (
              <Card
                key={session.session_id}
                onClick={() => handleSessionClick(session.session_id)}
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
                        className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 h-6 w-6 text-destructive hover:text-destructive flex-shrink-0"
                        title={t('sidebar.deleteConfirm')}
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
  )

  return (
    <>
      {showAnimalTypeSelector && (
        <AnimalTypeSelector
          onSelect={createNewSession}
          onCancel={() => setShowAnimalTypeSelector(false)}
        />
      )}

      {/* Desktop sidebar - visible on lg and up */}
      <div className="hidden lg:flex lg:w-80 bg-muted/30 border-r flex-col">
        {sidebarContent}
      </div>

      {/* Mobile drawer and floating buttons - visible on mobile only */}
      <div className="lg:hidden">
        <Sheet open={isDrawerOpen} onOpenChange={setIsDrawerOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className={`fixed top-1/2 -translate-y-1/2 z-[60] h-12 w-8 rounded-r-lg transition-all duration-300 bg-transparent border-0 ${
                isDrawerOpen
                  ? 'left-80 text-white hover:bg-white/10'
                  : 'left-0 hover:bg-muted/50'
              }`}
              title={t('sidebar.title')}
            >
              {isDrawerOpen ? <PanelLeftClose className="h-4 w-4 text-white" /> : <PanelLeftOpen className="h-4 w-4" />}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80 p-0">
            {sidebarContent}
          </SheetContent>
        </Sheet>

        {/* Floating new conversation button - only show when no session active */}
        {!currentSessionId && (
          <Button
            variant="default"
            size="icon"
            onClick={handleNewSessionClick}
            className="fixed bottom-20 right-4 z-40 h-14 w-14 rounded-full shadow-lg"
            title={t('sidebar.newChat')}
          >
            <Plus className="h-6 w-6" />
          </Button>
        )}
      </div>
    </>
  )
}
