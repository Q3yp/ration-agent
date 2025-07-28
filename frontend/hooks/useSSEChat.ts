'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Message, MessageType } from '@/types/chat'

interface UseSSEChatProps {
  sessionId: string
  endpoint?: string
}

interface UseSSEChatReturn {
  messages: Message[]
  isConnected: boolean
  isTyping: boolean
  connectionError: string | null
  sendMessage: (message: string) => Promise<void>
  retryConnection: () => void
}

export function useSSEChat({ sessionId, endpoint = 'http://localhost:8000' }: UseSSEChatProps): UseSSEChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  
  // Track if we should create a new bubble for the next chunk (using ref for immediate updates)
  const shouldCreateNewBubbleRef = useRef(false)
  // Track the ID of the current streaming bubble to update
  const [currentBubbleId, setCurrentBubbleId] = useState<string | null>(null)
  
  const eventSourceRef = useRef<EventSource | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsConnected(false)
    setIsTyping(false)
  }, [])

  const handleSSEMessage = useCallback((event: MessageEvent, eventType: string) => {
    try {
      const data = JSON.parse(event.data)

      switch (eventType) {
        case 'connected':
          setIsConnected(true)
          setConnectionError(null)
          console.log('SSE Connected:', data)
          break

        case 'thinking':
          setIsTyping(true)
          break

        case 'chunk':
          if (data.type === 'agent_chunk') {
            const messageId = data.message_id
            
            // Check flag and reset BEFORE setMessages to ensure immediate effect
            const shouldCreateNew = shouldCreateNewBubbleRef.current
            if (shouldCreateNew) {
              shouldCreateNewBubbleRef.current = false // Reset flag immediately
            }
            
            setMessages(prev => {
              // Check if there's an existing agent message
              const lastAgentIndex = prev.findLastIndex(msg => msg.type === 'agent')
              
              // Create new bubble if: 1) Tool flag is true, OR 2) No existing agent message
              if (shouldCreateNew || lastAgentIndex < 0) {
                // Create new bubble
                const newBubbleId = `${messageId}_bubble_${Date.now()}`
                setCurrentBubbleId(newBubbleId) // Track this bubble for updates
                
                const newBubble = {
                  id: newBubbleId,
                  type: 'agent' as MessageType,
                  content: data.content || '',
                  timestamp: data.timestamp || Date.now(),
                  isStreaming: true,
                  messageId: messageId
                }
                
                return [...prev, newBubble]
              }
              
              // Update the existing agent message
              return prev.map((msg, index) => 
                index === lastAgentIndex 
                  ? { ...msg, content: (msg.content || '') + (data.content || ''), isStreaming: true }
                  : msg
              )
            })
            setIsTyping(false)
          }
          break

        case 'tool_call':
          if (data.type === 'tool_call') {
            shouldCreateNewBubbleRef.current = true // Next chunk should create new bubble
            const message: Message = {
              id: data.tool_id || Date.now() + Math.random(),
              type: 'tool_call' as MessageType,
              content: `Calling ${data.tool_name}...`,
              timestamp: data.timestamp || Date.now(),
              toolName: data.tool_name,
              toolArgs: data.tool_args,
              toolCallId: data.tool_id,
            }
            setMessages(prev => [...prev, message])
          }
          break

        case 'tool_result':
          if (data.type === 'tool_result') {
            const message: Message = {
              id: Date.now() + Math.random(),
              type: 'tool_result' as MessageType,
              content: data.content,
              timestamp: data.timestamp || Date.now(),
              toolCallId: data.tool_call_id,
            }
            setMessages(prev => [...prev, message])
          }
          break

        case 'complete':
          if (data.type === 'agent_complete') {
            // Mark streaming message as complete
            setMessages(prev => prev.map(msg => 
              msg.messageId === data.message_id
                ? { ...msg, isStreaming: false }
                : msg
            ))
            setIsTyping(false)
          }
          break

        case 'error':
          console.error('SSE Error:', data)
          const errorMessage: Message = {
            id: Date.now() + Math.random(),
            type: 'error' as MessageType,
            content: data.content || 'An error occurred',
            timestamp: data.timestamp || Date.now(),
          }
          setMessages(prev => [...prev, errorMessage])
          setConnectionError(data.content || 'An error occurred')
          setIsTyping(false)
          break

        default:
          console.log('Unknown SSE event type:', eventType, data)
      }
    } catch (error) {
      console.error('Error parsing SSE message:', error, 'Raw data:', event.data)
    }
  }, [])

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim()) return

    try {
      // Reset state for new user message - set flag to create new bubble for agent response
      shouldCreateNewBubbleRef.current = true
      setCurrentBubbleId(null)
      
      // Add user message to messages immediately
      const userMessage: Message = {
        id: Date.now() + Math.random(),
        type: 'user' as MessageType,
        content: message.trim(),
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, userMessage])
      setIsTyping(true)
      setConnectionError(null)

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
        console.log('Request aborted')
        return
      }
      
      console.error('Error sending message:', error)
      setConnectionError(`Failed to send message: ${error.message}`)
      setIsTyping(false)
      
      // Add error message to chat
      const errorMessage: Message = {
        id: Date.now() + Math.random(),
        type: 'error' as MessageType,
        content: `Failed to send message: ${error.message}`,
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, errorMessage])
    }
  }, [endpoint, sessionId, handleSSEMessage])

  const retryConnection = useCallback(() => {
    setConnectionError(null)
    setIsConnected(false)
    // For SSE, connection is established per message, so we don't need to do anything here
    console.log('SSE: Ready to send messages')
  }, [])

  useEffect(() => {
    // SSE connections are established per message, so we just set initial state
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
    retryConnection,
  }
}