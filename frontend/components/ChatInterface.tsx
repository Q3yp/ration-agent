import { useState, useRef, useEffect } from 'react'
import { Send, AlertTriangle, Upload, Loader2, Square, MessageSquare } from 'lucide-react'
import MessageList from './MessageList'
import FileUpload from './FileUpload'
import HtmlArtifact from './HtmlArtifact'
import UserInputRequest from './UserInputRequest'
import { PlanUpgradeModal } from './PlanUpgradeModal'
import { useMessages } from '@/hooks/useMessages'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { AttachedFile, ArtifactData } from '@/types/chat'
import { getAuthHeaders } from '@/utils/authHeaders'
import { useI18n } from '@/contexts/I18nContext'

interface ChatInterfaceProps {
  sessionId: string
  endpoint?: string
  onTitleUpdate?: (sessionId: string, title: string) => void
  onTokenUsageUpdate?: (sessionId: string, tokenUsage: import('@/types/chat').TokenUsage) => void
  onArtifactChange?: (isOpen: boolean) => void
  readOnly?: boolean
}

export default function ChatInterface({
  sessionId,
  endpoint,
  onTitleUpdate,
  onTokenUsageUpdate,
  onArtifactChange,
  readOnly = false
}: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('')
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<AttachedFile[]>([])
  const [pendingFileNotifications, setPendingFileNotifications] = useState<string[]>([])
  const [currentArtifact, setCurrentArtifact] = useState<ArtifactData | null>(null)
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [feedbackContent, setFeedbackContent] = useState('')
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const isUserAtBottomRef = useRef(true)
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
    thinkingState,
    sendMessage,
    stopMessage,
    retryConnection,
    planLimitInfo,
    clearPlanLimitInfo,
    askUserState,
    resumeChat
  } = useMessages({
    sessionId,
    endpoint,
    autoLoadHistory: true,
    onTitleUpdate,
    onArtifactUpdate: setCurrentArtifact,
    onTokenUsageUpdate,
    // If readOnly, we might still want to load history, which useMessages does.
    // We don't strictly need to disable connection logic in useMessages unless we add a prop there too,
    // but for now we just hide UI.
  })
  const planLimitActive = planLimitInfo?.sessionId === sessionId

  // Track if user is at or near the bottom of the message container
  const checkIfAtBottom = () => {
    const container = messagesContainerRef.current
    if (!container) return true
    const threshold = 100 // pixels from bottom to consider "at bottom"
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold
  }

  const handleScroll = () => {
    isUserAtBottomRef.current = checkIfAtBottom()
  }

  // Clear artifact when switching sessions
  useEffect(() => {
    setCurrentArtifact(null)
  }, [sessionId])

  // Notify parent when artifact state changes
  useEffect(() => {
    onArtifactChange?.(!!currentArtifact)
  }, [currentArtifact, onArtifactChange])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest'
    })
  }

  // Only auto-scroll to bottom when user is already at the bottom
  useEffect(() => {
    if (isUserAtBottomRef.current) {
      scrollToBottom()
    }
  }, [messages, isTyping, isStreaming, thinkingState?.content, analysisState, formulationState])

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
    if (!inputValue.trim() || planLimitActive || readOnly) return

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

  const handleFeedbackSubmit = async () => {
    if (!feedbackContent.trim()) return

    setIsSubmittingFeedback(true)
    try {
      const res = await fetch(`${endpoint || '/api'}/feedback`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId,
          content: feedbackContent
        })
      })

      if (!res.ok) {
        throw new Error('Failed to submit feedback')
      }

      setFeedbackContent('')
      setShowFeedbackModal(false)
      // Optional: Show success toast
    } catch (error) {
      console.error('Error submitting feedback:', error)
      // Optional: Show error toast
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  return (
    <div className="flex flex-col md:flex-row h-full max-h-full overflow-hidden gap-4">
      {/* Chat Panel */}
      <Card className={`flex flex-col h-full overflow-hidden transition-all duration-300 ${currentArtifact ? 'w-full md:w-1/2' : 'w-full'
        }`}>
        {/* Connection Status */}
        <div className="px-4 py-3 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  readOnly
                    ? "outline"
                    : isLoading
                      ? "secondary"
                      : connectionState === 'connected'
                        ? "default"
                        : connectionState === 'connecting' || isTyping
                          ? "secondary"
                          : "destructive"
                }
                className="flex items-center gap-1"
              >
                {readOnly ? (
                  <>
                    <span className="h-2 w-2 rounded-full bg-gray-400" />
                    Viewing History
                  </>
                ) : isLoading ? (
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
              {error && !isLoading && !readOnly && (
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

            {!readOnly && (
              <Dialog open={showFeedbackModal} onOpenChange={setShowFeedbackModal}>
                <DialogTrigger asChild>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-auto py-1 px-3 text-xs gap-1.5 font-medium shadow-sm hover:bg-secondary/80"
                  >
                    <MessageSquare className="h-3.5 w-3.5" />
                    <span>{t('feedback.buttonLabel')}</span>
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t('feedback.dialogTitle')}</DialogTitle>
                    <DialogDescription>
                      {t('feedback.dialogDescription')}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <Label htmlFor="feedback">{t('feedback.buttonLabel')}</Label>
                      <Textarea
                        id="feedback"
                        placeholder={t('feedback.placeholder')}
                        value={feedbackContent}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFeedbackContent(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowFeedbackModal(false)}>
                      {t('common.buttons.cancel')}
                    </Button>
                    <Button onClick={handleFeedbackSubmit} disabled={isSubmittingFeedback || !feedbackContent.trim()}>
                      {isSubmittingFeedback && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {t('feedback.submit')}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
          {error && !isLoading && !readOnly ? (
            <div className="mt-2 flex items-center text-sm text-muted-foreground">
              <AlertTriangle className="h-4 w-4 mr-1" />
              {error}
            </div>
          ) : null}
        </div>

        {planLimitActive && !readOnly && (
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
        <CardContent
          ref={messagesContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-2 sm:p-4 space-y-3 sm:space-y-4 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 hover:scrollbar-thumb-gray-400 min-h-0"
        >
          <MessageList
            messages={messages}
            isTyping={isTyping || isStreaming}
            analysisState={analysisState}
            formulationState={formulationState}
            thinkingState={thinkingState}
            onArtifactOpen={setCurrentArtifact}
            onFileDownload={handleFileDownload}
            sessionId={sessionId}
          />
          {/* Ask User Input Request */}
          {askUserState?.isActive && !readOnly && (
            <UserInputRequest
              description={askUserState.description}
              questions={askUserState.questions}
              onSubmit={resumeChat}
              disabled={isTyping || isStreaming}
            />
          )}
          <div ref={messagesEndRef} />
        </CardContent>

        {/* File Upload Section */}
        {showFileUpload && !readOnly && (
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
        {!readOnly && (
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
        )}
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
