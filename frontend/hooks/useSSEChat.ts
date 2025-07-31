'use client'

import { useState, useRef, useEffect, useCallback, useReducer } from 'react'
import { Message, MessageType, AttachedFile } from '@/types/chat'
import { getRoleInfo } from '@/utils/roleMapping'

interface MessageState {
  messages: Message[]
  shouldCreateNewBubble: boolean
  currentBubbleId: string | null
}

type MessageAction = 
  | { type: 'SET_INITIAL_MESSAGES'; payload: Message[] }
  | { type: 'ADD_USER_MESSAGE'; payload: Message }
  | { type: 'ADD_CHUNK'; payload: { messageId: string; content: string; timestamp: number } }
  | { type: 'ADD_TOOL_CALL'; payload: Message }
  | { type: 'ADD_TOOL_RESULT'; payload: Message }
  | { type: 'ADD_ROLE_TRANSITION'; payload: Message }
  | { type: 'ADD_ERROR'; payload: Message }
  | { type: 'MARK_COMPLETE'; payload: { messageId: string } }
  | { type: 'SET_NEW_BUBBLE_FLAG'; payload: boolean }
  | { type: 'RESET_FOR_NEW_MESSAGE' }

function messageReducer(state: MessageState, action: MessageAction): MessageState {
  switch (action.type) {
    case 'SET_INITIAL_MESSAGES':
      return {
        ...state,
        messages: action.payload,
        shouldCreateNewBubble: false,
        currentBubbleId: null
      }
    
    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
        shouldCreateNewBubble: true, // Next agent chunk should create new bubble
        currentBubbleId: null
      }
    
    case 'ADD_CHUNK': {
      const { messageId, content, timestamp } = action.payload
      const lastAgentIndex = state.messages.findLastIndex(msg => msg.type === 'agent')
      
      // Create new bubble if flag is set OR no existing agent message
      if (state.shouldCreateNewBubble || lastAgentIndex < 0) {
        const newBubbleId = `${messageId}_bubble_${Date.now()}`
        const newBubble: Message = {
          id: newBubbleId,
          type: 'agent' as MessageType,
          content: content || '',
          timestamp: timestamp,
          isStreaming: true,
          messageId: messageId
        }
        
        return {
          ...state,
          messages: [...state.messages, newBubble],
          shouldCreateNewBubble: false, // Reset flag
          currentBubbleId: newBubbleId
        }
      }
      
      // Update existing agent message
      return {
        ...state,
        messages: state.messages.map((msg, index) => 
          index === lastAgentIndex 
            ? { ...msg, content: (msg.content || '') + (content || ''), isStreaming: true }
            : msg
        )
      }
    }
    
    case 'ADD_TOOL_CALL':
      return {
        ...state,
        messages: [...state.messages, action.payload],
        shouldCreateNewBubble: true // Next chunk should create new bubble
      }
    
    case 'ADD_TOOL_RESULT':
      return {
        ...state,
        messages: [...state.messages, action.payload]
      }
    
    case 'ADD_ROLE_TRANSITION':
      return {
        ...state,
        messages: [...state.messages, action.payload],
        shouldCreateNewBubble: true // Next chunk should create new bubble
      }
    
    case 'ADD_ERROR':
      return {
        ...state,
        messages: [...state.messages, action.payload]
      }
    
    case 'MARK_COMPLETE':
      return {
        ...state,
        messages: state.messages.map(msg => 
          msg.messageId === action.payload.messageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      }
    
    case 'SET_NEW_BUBBLE_FLAG':
      return {
        ...state,
        shouldCreateNewBubble: action.payload
      }
    
    case 'RESET_FOR_NEW_MESSAGE':
      return {
        ...state,
        shouldCreateNewBubble: true,
        currentBubbleId: null
      }
    
    default:
      return state
  }
}

interface UseSSEChatProps {
  sessionId: string
  endpoint?: string
  onTitleUpdate?: (sessionId: string, title: string) => void
}

interface UseSSEChatReturn {
  messages: Message[]
  isConnected: boolean
  isTyping: boolean
  connectionError: string | null
  sendMessage: (message: string, filesToShow?: AttachedFile[]) => Promise<void>
  retryConnection: () => void
  setInitialMessages: (messages: Message[]) => void
}

export function useSSEChat({ sessionId, endpoint = 'http://localhost:8000', onTitleUpdate }: UseSSEChatProps): UseSSEChatReturn {
  const [messageState, dispatch] = useReducer(messageReducer, {
    messages: [],
    shouldCreateNewBubble: false,
    currentBubbleId: null
  })
  
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  
  const eventSourceRef = useRef<EventSource | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      try {
        eventSourceRef.current.close()
      } catch (error) {
        // Ignore errors during cleanup
        console.debug('Error during EventSource cleanup:', error)
      }
      eventSourceRef.current = null
    }
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort()
      } catch (error) {
        // Ignore abort errors during cleanup
        console.debug('Error during abort cleanup:', error)
      }
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
            dispatch({
              type: 'ADD_CHUNK',
              payload: {
                messageId: data.message_id,
                content: data.content || '',
                timestamp: data.timestamp || Date.now()
              }
            })
            setIsTyping(false)
          }
          break

        case 'tool_call':
          if (data.type === 'tool_call') {
            const message: Message = {
              id: data.tool_id || `${Date.now()}_${Math.random()}`,
              type: 'tool_call' as MessageType,
              content: `Calling ${data.tool_name}...`,
              timestamp: data.timestamp || Date.now(),
              toolName: data.tool_name,
              toolArgs: data.tool_args,
              toolCallId: data.tool_id,
            }
            dispatch({ type: 'ADD_TOOL_CALL', payload: message })
          }
          break

        case 'tool_result':
          if (data.type === 'tool_result') {
            const message: Message = {
              id: `${Date.now()}_${Math.random()}`,
              type: 'tool_result' as MessageType,
              content: data.content,
              timestamp: data.timestamp || Date.now(),
              toolCallId: data.tool_call_id,
            }
            dispatch({ type: 'ADD_TOOL_RESULT', payload: message })
          }
          break

        case 'role_transition':
          if (data.type === 'role_transition') {
            const roleInfo = getRoleInfo(data.to_role)
            const message: Message = {
              id: `${Date.now()}_${Math.random()}`,
              type: 'role_transition' as MessageType,
              content: roleInfo.transitionMessage,
              timestamp: data.timestamp || Date.now(),
              toRole: data.to_role,
            }
            dispatch({ type: 'ADD_ROLE_TRANSITION', payload: message })
          }
          break

        case 'title_update':
          if (data.type === 'title_update') {
            // Call the title update callback if provided
            onTitleUpdate?.(data.session_id, data.title)
          }
          break

        case 'complete':
          if (data.type === 'agent_complete') {
            dispatch({
              type: 'MARK_COMPLETE',
              payload: { messageId: data.message_id }
            })
            setIsTyping(false)
          }
          break

        case 'error':
          console.error('SSE Error:', data)
          const errorMessage: Message = {
            id: `${Date.now()}_${Math.random()}`,
            type: 'error' as MessageType,
            content: data.content || 'An error occurred',
            timestamp: data.timestamp || Date.now(),
          }
          dispatch({ type: 'ADD_ERROR', payload: errorMessage })
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

  const sendMessage = useCallback(async (message: string, filesToShow?: AttachedFile[]) => {
    if (!message.trim()) return

    try {
      // Add user message to messages immediately
      const userMessage: Message = {
        id: `${Date.now()}_${Math.random()}`,
        type: 'user' as MessageType,
        content: message.trim(),
        timestamp: Date.now(),
        attachedFiles: filesToShow,
      }
      dispatch({ type: 'ADD_USER_MESSAGE', payload: userMessage })
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
        id: `${Date.now()}_${Math.random()}`,
        type: 'error' as MessageType,
        content: `Failed to send message: ${error.message}`,
        timestamp: Date.now(),
      }
      dispatch({ type: 'ADD_ERROR', payload: errorMessage })
    }
  }, [endpoint, sessionId, handleSSEMessage])

  const retryConnection = useCallback(() => {
    setConnectionError(null)
    setIsConnected(false)
    // For SSE, connection is established per message, so we don't need to do anything here
    console.log('SSE: Ready to send messages')
  }, [])

  const setInitialMessages = useCallback((initialMessages: Message[]) => {
    dispatch({ type: 'SET_INITIAL_MESSAGES', payload: initialMessages })
  }, [])

  useEffect(() => {
    // SSE connections are established per message, so we just set initial state
    setIsConnected(true)
    setConnectionError(null)

    return cleanup
  }, [cleanup])

  return {
    messages: messageState.messages,
    isConnected,
    isTyping,
    connectionError,
    sendMessage,
    retryConnection,
    setInitialMessages,
  }
}