'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, AlertTriangle, Upload, Loader2, Square } from 'lucide-react'
import MessageList from './MessageList'
import FileUpload from './FileUpload'
import HtmlArtifact from './HtmlArtifact'
import { PlanUpgradeModal } from './PlanUpgradeModal'
import { useMessages } from '@/hooks/useMessages'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AttachedFile, ArtifactData } from '@/types/chat'
import { getAuthHeaders } from '@/utils/authHeaders'
import { useI18n } from '@/contexts/I18nContext'

interface ChatInterfaceProps {
  sessionId: string
  endpoint?: string
  onTitleUpdate?: (sessionId: string, title: string) => void
  onTokenUsageUpdate?: (sessionId: string, tokenUsage: import('@/types/chat').TokenUsage) => void
}

export default function ChatInterface({ sessionId, endpoint, onTitleUpdate, onTokenUsageUpdate }: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('')
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<AttachedFile[]>([])
  const [pendingFileNotifications, setPendingFileNotifications] = useState<string[]>([])
  const [currentArtifact, setCurrentArtifact] = useState<ArtifactData | null>(null)
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { t } = useI18n()

  const {
    messages,
    isLoading,
    isStreaming,
    isConnected,
    connectionState,
    error,
    isTyping,
    analysisState,
    formulationState,
    sendMessage,
    stopMessage,
    retryConnection,
    planLimitInfo,
    clearPlanLimitInfo
  } = useMessages({
    sessionId,
    endpoint,
    autoLoadHistory: true,
    onTitleUpdate,
    onArtifactUpdate: setCurrentArtifact,
    onTokenUsageUpdate
  })
  const planLimitActive = planLimitInfo?.sessionId === sessionId

  // Clear artifact when switching sessions
  useEffect(() => {
    setCurrentArtifact(null)
  }, [sessionId])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest'
    })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleFileUploaded = (uploadedFile: { name: string; size: number; originalName?: string }) => {
    // Buffer the file notification instead of sending immediately
    const fileName = uploadedFile.originalName || uploadedFile.name
    setPendingFileNotifications(prev => {
      // Avoid duplicate notifications
      if (prev.includes(fileName)) {
        return prev
      }
      return [...prev, fileName]
    })
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || planLimitActive) return

    let messageToSend = inputValue.trim()
    
    // Prepend file notifications to the message using special format
    if (pendingFileNotifications.length > 0) {
      const fileNotificationText = pendingFileNotifications
        .map(fileName => `[FILE_UPLOAD]${fileName}[/FILE_UPLOAD]`)
        .join('\n')
      messageToSend = `${fileNotificationText}\n\n${messageToSend}`
      
      // Clear pending notifications
      setPendingFileNotifications([])
    }
    
    const filesToShow = uploadedFiles.length > 0 ? [...uploadedFiles] : undefined
    
    // Clear input and files immediately
    setInputValue('')
    setUploadedFiles([])
    setShowFileUpload(false)
    
    try {
      await sendMessage(messageToSend, filesToShow)
    } catch (error) {
      console.error('Failed to send message:', error)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleFileDownload = async (filename: string, sessionId: string) => {
    try {
      const downloadUrl = `${endpoint || '/api'}/files/download/${sessionId}/${encodeURIComponent(filename)}`

      const res = await fetch(downloadUrl, {
        method: 'GET',
        headers: {
          ...getAuthHeaders(),
          'Accept': 'application/octet-stream'
        },
      })

      if (!res.ok) {
        throw new Error(t('errors.downloadFailed', { code: res.status.toString() }))
      }

      const blob = await res.blob()
      const objectUrl = window.URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = objectUrl
      link.download = filename
      link.style.display = 'none'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      // 延迟释放 URL，确保浏览器已开始下载
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
      
    } catch (error) {
      console.error('File download failed:', error)
      // Could add toast notification here
    }
  }

  return (
    <div className="flex flex-col md:flex-row h-full max-h-full overflow-hidden gap-4">
      {/* Chat Panel */}
      <Card className={`flex flex-col h-full overflow-hidden transition-all duration-300 ${
        currentArtifact ? 'w-full md:w-1/2' : 'w-full'
      }`}>
        {/* Connection Status */}
        <div className="px-4 py-3 border-b">
          <div className="flex items-center justify-between">
            <Badge
              variant={
                isLoading
                  ? "secondary"
                  : connectionState === 'connected'
                  ? "default"
                  : connectionState === 'connecting' || isTyping
                  ? "secondary"
                  : "destructive"
              }
              className="flex items-center gap-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {t('common.statuses.loading')}
                </>
              ) : connectionState === 'connected' ? (
                <>{t('common.statuses.connected')}</>
              ) : connectionState === 'connecting' || isTyping ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {t('common.statuses.connecting')}
                </>
              ) : (
                <>{t('common.statuses.error')}</>
              )}
            </Badge>
            {error && !isLoading && (
              <Button
                variant="ghost"
                size="sm"
                onClick={retryConnection}
                className="text-xs"
              >
                {t('common.buttons.retry')}
              </Button>
            )}
          </div>
          {error && !isLoading ? (
            <div className="mt-2 flex items-center text-sm text-muted-foreground">
              <AlertTriangle className="h-4 w-4 mr-1" />
              {error}
            </div>
          ) : null}
        </div>

        {planLimitActive && (
          <div className="px-4 py-3 border-b bg-amber-50">
            <div className="space-y-2">
              <div>
                <p className="text-sm font-semibold text-amber-900">
                  {t('chat.promptLimitTitle')}
                </p>
                <p className="text-xs text-amber-800 leading-relaxed">
                  {t('chat.promptLimitBody')}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => setShowUpgradeModal(true)}
                >
                  {t('chat.promptLimitCTA')}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearPlanLimitInfo}
                >
                  {t('chat.promptLimitDismiss')}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        <CardContent className="flex-1 overflow-y-auto p-2 sm:p-4 space-y-3 sm:space-y-4 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 hover:scrollbar-thumb-gray-400 min-h-0">
          <MessageList
            messages={messages}
            isTyping={isTyping || isStreaming}
            analysisState={analysisState}
            formulationState={formulationState}
            onArtifactOpen={setCurrentArtifact}
            onFileDownload={handleFileDownload}
            sessionId={sessionId}
          />
          <div ref={messagesEndRef} />
        </CardContent>

        {/* File Upload Section */}
        {showFileUpload && (
          <div className="border-t p-4">
            <FileUpload 
              sessionId={sessionId} 
              endpoint={endpoint}
              onFilesChange={setUploadedFiles}
              onFileUploaded={handleFileUploaded}
            />
          </div>
        )}

        {/* Input */}
        <div className="border-t p-3 sm:p-4">
          <div className="flex space-x-2">
            <Button
              variant={showFileUpload ? "default" : "outline"}
              size="icon"
              onClick={() => setShowFileUpload(!showFileUpload)}
              disabled={!isConnected || isLoading || isTyping || planLimitActive}
              className="h-10 w-10 sm:h-9 sm:w-9"
            >
              <Upload className="h-4 w-4" />
            </Button>
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.inputPlaceholder')}
              disabled={!isConnected || isTyping || isStreaming || isLoading || planLimitActive}
              className="flex-1 text-base sm:text-sm"
            />
            {isTyping || isStreaming ? (
              <Button
                onClick={stopMessage}
                variant="destructive"
                size="icon"
                className="h-10 w-10 sm:h-9 sm:w-9"
              >
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || !isConnected || isLoading || planLimitActive}
                size="icon"
                className="h-10 w-10 sm:h-9 sm:w-9"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          {uploadedFiles.length > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              • {uploadedFiles.length} files attached
            </div>
          )}
        </div>
      </Card>

      {/* Artifact Panel */}
      {currentArtifact && (
        <div className="fixed inset-0 md:relative md:w-1/2 h-full transition-all duration-300 z-40 md:z-auto bg-background">
          <HtmlArtifact
            title={currentArtifact.title}
            description={currentArtifact.description}
            htmlContent={currentArtifact.html_content}
            onClose={() => setCurrentArtifact(null)}
          />
        </div>
      )}

      {/* Plan Upgrade Modal */}
      <PlanUpgradeModal
        open={showUpgradeModal}
        onOpenChange={setShowUpgradeModal}
      />
    </div>
  )
}
