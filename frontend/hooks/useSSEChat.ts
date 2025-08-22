'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Message, MessageType, AttachedFile, ArtifactData } from '@/types/chat'

interface UseSSEChatProps {
  sessionId: string
  endpoint?: string
  onTitleUpdate?: (sessionId: string, title: string) => void
  onArtifactUpdate?: (artifactData: ArtifactData | null) => void
}

interface UseSSEChatReturn {
  messages: Message[]
  isConnected: boolean
  isTyping: boolean
  connectionError: string | null
  sendMessage: (message: string, filesToShow?: AttachedFile[]) => Promise<void>
  stopMessage: () => Promise<void>
  retryConnection: () => void
  setInitialMessages: (messages: Message[]) => void
}

export function useSSEChat({ sessionId, endpoint = 'http://localhost:8000', onTitleUpdate, onArtifactUpdate }: UseSSEChatProps): UseSSEChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  
  const abortControllerRef = useRef<AbortController | null>(null)
  const currentStreamingMessageRef = useRef<string | null>(null)

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort()
      } catch (error) {
        // Ignore abort errors during cleanup
      }
      abortControllerRef.current = null
    }
    setIsConnected(false)
    setIsTyping(false)
    currentStreamingMessageRef.current = null
  }, [])

  const handleSSEMessage = useCallback((event: MessageEvent, eventType: string) => {
    try {
      const data = JSON.parse(event.data)

      switch (eventType) {
        case 'connected':
          setIsConnected(true)
          setConnectionError(null)
          break


        case 'message':
          const message: Message = {
            id: data.id,
            type: data.type as MessageType,
            content: data.content,
            timestamp: data.timestamp,
            metadata: data.metadata
          }

          // Handle different message types
          if (message.type === 'agent' && message.metadata?.is_streaming) {
            // Streaming agent message - accumulate content
            setMessages(prev => {
              // Find existing message with same ID
              const existingIndex = prev.findIndex(msg => msg.id === message.id)
              
              if (existingIndex >= 0) {
                // Update existing message with same ID
                const updated = [...prev]
                updated[existingIndex] = {
                  ...updated[existingIndex],
                  content: updated[existingIndex].content + message.content
                }
                return updated
              } else {
                // Create new streaming message (new ID means new agent response)
                return [...prev, message]
              }
            })
          } else {
            // Non-streaming message - add directly
            setMessages(prev => [...prev, message])
            
            // Handle artifact messages
            if (message.type === 'artifact' && message.metadata && onArtifactUpdate) {
              const artifactData: ArtifactData = {
                title: message.metadata.title || message.content,
                description: message.metadata.description || '',
                html_content: message.metadata.html_content || ''
              }
              onArtifactUpdate(artifactData)
            }
          }
          break

        case 'title_update':
          if (data.type === 'title_update') {
            onTitleUpdate?.(data.session_id, data.title)
          }
          break

        case 'artifact_loading':
          if (data.type === 'artifact_loading') {
            // Show loading artifact
            onArtifactUpdate?.({ 
              title: '正在创建内容...', 
              description: '请稍候，正在生成内容中...', 
              html_content: `
                <!DOCTYPE html>
                <html lang="zh">
                <head>
                  <meta charset="UTF-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1.0">
                  <title>正在创建内容</title>
                  <style>
                    body {
                      margin: 0;
                      padding: 0;
                      display: flex;
                      justify-content: center;
                      align-items: center;
                      min-height: 100vh;
                      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
                    }
                    .loading-container {
                      text-align: center;
                      color: white;
                    }
                    .spinner {
                      width: 60px;
                      height: 60px;
                      border: 4px solid rgba(255, 255, 255, 0.3);
                      border-top: 4px solid white;
                      border-radius: 50%;
                      animation: spin 1s linear infinite;
                      margin: 0 auto 24px;
                    }
                    @keyframes spin {
                      0% { transform: rotate(0deg); }
                      100% { transform: rotate(360deg); }
                    }
                    .loading-text {
                      font-size: 18px;
                      font-weight: 500;
                      margin-bottom: 8px;
                    }
                    .loading-subtitle {
                      font-size: 14px;
                      opacity: 0.8;
                    }
                  </style>
                </head>
                <body>
                  <div class="loading-container">
                    <div class="spinner"></div>
                    <div class="loading-text">正在创建内容</div>
                    <div class="loading-subtitle">请稍候...</div>
                  </div>
                </body>
                </html>
              `,
              isLoading: true 
            })
          }
          break

        case 'complete':
          if (data.type === 'agent_complete') {
            // Mark streaming message as complete
            setMessages(prev => prev.map(msg => 
              msg.id === currentStreamingMessageRef.current
                ? { ...msg, metadata: { ...msg.metadata, is_streaming: false } }
                : msg
            ))
            setIsTyping(false)
            currentStreamingMessageRef.current = null
          }
          break

        case 'stopped':
          if (data.type === 'agent_stopped') {
            console.log('Agent execution stopped:', data.message)
            setIsTyping(false)
            currentStreamingMessageRef.current = null
          }
          break

        case 'error':
          console.error('SSE Error:', data)
          setConnectionError(data.content || 'An error occurred')
          setIsTyping(false)
          currentStreamingMessageRef.current = null
          break

        default:
          // Ignore unknown event types
      }
    } catch (error) {
      console.error('Error parsing SSE message:', error, 'Raw data:', event.data)
    }
  }, [onTitleUpdate, onArtifactUpdate])

  const sendMessage = useCallback(async (message: string, filesToShow?: AttachedFile[]) => {
    if (!message.trim()) return

    try {
      // Add user message immediately
      const userMessage: Message = {
        id: `user_${Date.now()}_${Math.random()}`,
        type: 'user' as MessageType,
        content: message.trim(),
        timestamp: Date.now(),
        metadata: { attached_files: filesToShow },
      }
      setMessages(prev => [...prev, userMessage])
      setIsTyping(true)
      setConnectionError(null)
      currentStreamingMessageRef.current = null

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController()

      // Send message to SSE endpoint
      const response = await fetch(`${endpoint}/chat/stream/${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ message: message.trim() }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('No response body for streaming')
      }

      // Create EventSource-like reader for the stream
      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n')

          let eventType = 'message'
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              eventData = line.slice(5).trim()
            } else if (line === '' && eventData) {
              // End of event, process it
              const mockEvent = { data: eventData } as MessageEvent
              handleSSEMessage(mockEvent, eventType)
              eventType = 'message'
              eventData = ''
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Stream aborted (stop button clicked)')
        return
      }
      
      console.error('Error sending message:', error)
      setConnectionError(`Failed to send message: ${error.message}`)
      setIsTyping(false)
      currentStreamingMessageRef.current = null
    }
  }, [endpoint, sessionId, handleSSEMessage])

  const stopMessage = useCallback(async () => {
    try {
      // Send stop request to backend
      const response = await fetch(`${endpoint}/chat/stop/${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (!response.ok) {
        throw new Error(`Failed to stop: ${response.statusText}`)
      }
      
      const result = await response.json()
      console.log('Stop requested:', result.message)
      
      setIsTyping(false)
      currentStreamingMessageRef.current = null
      
    } catch (error: any) {
      console.error('Error stopping message:', error)
      setConnectionError(`Failed to stop: ${error.message}`)
    }
  }, [endpoint, sessionId])

  const retryConnection = useCallback(() => {
    setConnectionError(null)
    setIsConnected(false)
  }, [])

  const setInitialMessages = useCallback((initialMessages: Message[]) => {
    setMessages(initialMessages)
    currentStreamingMessageRef.current = null
  }, [])

  useEffect(() => {
    setIsConnected(true)
    setConnectionError(null)
    return cleanup
  }, [cleanup])

  return {
    messages,
    isConnected,
    isTyping,
    connectionError,
    sendMessage,
    stopMessage,
    retryConnection,
    setInitialMessages,
  }
}