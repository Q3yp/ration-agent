'use client'

import { useState } from 'react'
import { MessageCircle, User, LogOut, Database, BookOpen, Menu, X } from 'lucide-react'
import ChatInterface from '@/components/ChatInterface'
import ConversationSidebar from '@/components/ConversationSidebar'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuthContext } from '@/contexts/AuthContext'
import Link from 'next/link'
import { useI18n } from '@/contexts/I18nContext'
import { LocaleToggle } from '@/components/LocaleToggle'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu'

export default function Home() {
  const { user, logout } = useAuthContext()
  const { t } = useI18n()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chatKey, setChatKey] = useState(0) // Force ChatInterface re-render when session changes
  const [sessionTitles, setSessionTitles] = useState<Record<string, string>>({})
  const [sessionTokenUsage, setSessionTokenUsage] = useState<Record<string, import('@/types/chat').TokenUsage>>({})
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
      <main className="h-screen overflow-hidden bg-gradient-to-br from-background to-muted">
        <div className="h-full flex overflow-hidden">
          {/* Floating Language Toggle - Mobile only */}
          <div className="sm:hidden fixed top-[74px] right-4 z-50">
            <LocaleToggle />
          </div>

          {/* Sidebar */}
          <ConversationSidebar
            currentSessionId={sessionId}
            onSessionSelect={handleSessionSelect}
            onNewSession={handleNewSession}
            sessionTitles={sessionTitles}
            sessionTokenUsage={sessionTokenUsage}
          />

          {/* Main content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <header className="py-2 sm:py-4 px-3 sm:px-6 border-b">
              <div className="flex justify-between items-center gap-2 sm:gap-4">
                <h1 className="text-lg sm:text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent truncate">
                  {t('common.appName')}
                </h1>

                {/* Desktop Navigation - Hidden on mobile */}
                <div className="hidden sm:flex items-center gap-1 md:gap-2">
                  <span className="hidden md:inline text-xs md:text-sm text-muted-foreground truncate max-w-xs">
                    {user?.username ? t('common.welcomeUser', { name: user.username }) : t('common.welcomeGeneric')}
                  </span>
                  <Link href="/guide">
                    <Button variant="outline" size="sm">
                      <BookOpen className="h-4 w-4 md:mr-1" />
                      <span className="hidden md:inline">{t('chat.guide')}</span>
                    </Button>
                  </Link>
                  <Link href="/feedbases">
                    <Button variant="outline" size="sm">
                      <Database className="h-4 w-4 md:mr-1" />
                      <span className="hidden md:inline">{t('chat.feedbase')}</span>
                    </Button>
                  </Link>
                  {user?.is_superuser && (
                    <Link href="/admin">
                      <Button variant="outline" size="sm">
                        <User className="h-4 w-4 md:mr-1" />
                        <span className="hidden md:inline">{t('chat.admin')}</span>
                      </Button>
                    </Link>
                  )}
                  <LocaleToggle />
                  <Button variant="outline" size="sm" onClick={logout}>
                    <LogOut className="h-4 w-4 md:mr-1" />
                    <span className="hidden md:inline">{t('common.buttons.logout')}</span>
                  </Button>
                </div>

                {/* Mobile Menu - Visible only on mobile */}
                <div className="flex sm:hidden items-center gap-2">
                  <DropdownMenu open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem asChild>
                        <Link href="/guide" className="flex items-center gap-2">
                          <BookOpen className="h-4 w-4" />
                          {t('chat.guide')}
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link href="/feedbases" className="flex items-center gap-2">
                          <Database className="h-4 w-4" />
                          {t('chat.feedbase')}
                        </Link>
                      </DropdownMenuItem>
                      {user?.is_superuser && (
                        <DropdownMenuItem asChild>
                          <Link href="/admin" className="flex items-center gap-2">
                            <User className="h-4 w-4" />
                            {t('chat.admin')}
                          </Link>
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={logout} className="flex items-center gap-2">
                        <LogOut className="h-4 w-4" />
                        {t('common.buttons.logout')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </header>
          
          <div className="flex-1 p-3 sm:p-6 min-h-0">
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
                <Card className="w-full max-w-md mx-4">
                  <CardContent className="p-6 text-center">
                    <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground mb-3">{t('chat.selectPrompt')}</p>
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
