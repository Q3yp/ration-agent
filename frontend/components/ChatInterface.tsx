'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, AlertTriangle, Upload, Loader2, Square } from 'lucide-react'
import MessageList from './MessageList'
import FileUpload from './FileUpload'
import HtmlArtifact from './HtmlArtifact'
import { useMessages } from '@/hooks/useMessages'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AttachedFile, ArtifactData } from '@/types/chat'
import { getAuthHeaders } from '@/utils/authHeaders'

interface ChatInterfaceProps {
  sessionId: string
  endpoint?: string
  onTitleUpdate?: (sessionId: string, title: string) => void
}

export default function ChatInterface({ sessionId, endpoint, onTitleUpdate }: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('')
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<AttachedFile[]>([])
  const [pendingFileNotifications, setPendingFileNotifications] = useState<string[]>([])
  const [currentArtifact, setCurrentArtifact] = useState<ArtifactData | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const {
    messages,
    isLoading,
    isStreaming,
    isConnected,
    connectionState,
    error,
    isTyping,
    sendMessage,
    stopMessage,
    retryConnection
  } = useMessages({
    sessionId,
    endpoint,
    autoLoadHistory: true,
    onTitleUpdate,
    onArtifactUpdate: setCurrentArtifact
  })

  // Clear artifact when switching sessions
  useEffect(() => {
    setCurrentArtifact(null)
  }, [sessionId])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
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
    if (!inputValue.trim()) return

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
        throw new Error(`下载失败: HTTP ${res.status}`)
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
    <div className="flex h-full max-h-full overflow-hidden gap-4">
      {/* Chat Panel */}
      <Card className={`flex flex-col overflow-hidden transition-all duration-300 ${
        currentArtifact ? 'w-1/2' : 'w-full'
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
                  正在加载对话...
                </>
              ) : connectionState === 'connected' ? (
                <>已连接</>
              ) : connectionState === 'connecting' || isTyping ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  正在连接...
                </>
              ) : (
                <>连接错误</>
              )}
            </Badge>
            {error && !isLoading && (
              <Button
                variant="ghost"
                size="sm"
                onClick={retryConnection}
                className="text-xs"
              >
                重试
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

        {/* Messages */}
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 hover:scrollbar-thumb-gray-400 min-h-0">
          <MessageList
            messages={messages}
            isTyping={isTyping || isStreaming}
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
        <div className="border-t p-4">
          <div className="flex space-x-2">
            <Button
              variant={showFileUpload ? "default" : "outline"}
              size="icon"
              onClick={() => setShowFileUpload(!showFileUpload)}
              disabled={!isConnected || isLoading || isTyping}
              title="切换文件上传"
            >
              <Upload className="h-4 w-4" />
            </Button>
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入您的消息..."
              disabled={!isConnected || isTyping || isStreaming || isLoading}
              className="flex-1"
            />
            {isTyping || isStreaming ? (
              <Button
                onClick={stopMessage}
                variant="destructive"
                size="icon"
                title="停止执行"
              >
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || !isConnected || isLoading}
                size="icon"
                title="发送消息"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            按 Enter 发送 • Shift+Enter 换行 • {showFileUpload ? '文件上传已启用' : '点击 📁 上传文件'} • 使用服务器发送事件
            {uploadedFiles.length > 0 && (
              <span className="ml-2 text-primary">• 已附加 {uploadedFiles.length} 个文件</span>
            )}
          </div>
        </div>
      </Card>

      {/* Artifact Panel */}
      {currentArtifact && (
        <div className="w-1/2 h-full transition-all duration-300">
          <HtmlArtifact
            title={currentArtifact.title}
            description={currentArtifact.description}
            htmlContent={currentArtifact.html_content}
            onClose={() => setCurrentArtifact(null)}
          />
        </div>
      )}
    </div>
  )
}