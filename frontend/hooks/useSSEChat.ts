'use client'

import { useState, useRef, useEffect, useCallback, useReducer } from 'react'
import { Message, MessageType, AttachedFile, ArtifactData } from '@/types/chat'
import { getRoleInfo } from '@/utils/roleMapping'
import { parseArtifactData, cleanContentForDisplay } from '@/utils/artifactParser'

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
      }
      eventSourceRef.current = null
    }
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
  }, [])

  const handleSSEMessage = useCallback((event: MessageEvent, eventType: string) => {
    try {
      const data = JSON.parse(event.data)

      switch (eventType) {
        case 'connected':
          setIsConnected(true)
          setConnectionError(null)
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
            // Don't set isTyping to false here - agent is still working
            // Only set to false on 'complete' or 'stopped' events
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
            // Check if the tool result contains artifact data
            const artifactData = parseArtifactData(data.content);
            
            // If artifact data is found, update the artifact panel (auto-open for live session)
            // This will replace any loading state that was shown earlier
            if (artifactData && onArtifactUpdate) {
              onArtifactUpdate(artifactData);
            }
            
            // Keep the original content (including artifact data) so MessageBubble can detect it
            const message: Message = {
              id: `${Date.now()}_${Math.random()}`,
              type: 'tool_result' as MessageType,
              content: data.content, // Keep original content with artifact data
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
              actionData: data.action_data
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

        case 'artifact_loading':
          if (data.type === 'artifact_loading') {
            // Open artifact panel with loading state
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
                    .dots {
                      animation: dots 1.5s steps(4, end) infinite;
                    }
                    @keyframes dots {
                      0%, 20% { content: ''; }
                      40% { content: '.'; }
                      60% { content: '..'; }
                      80%, 100% { content: '...'; }
                    }
                  </style>
                </head>
                <body>
                  <div class="loading-container">
                    <div class="spinner"></div>
                    <div class="loading-text">正在创建内容</div>
                    <div class="loading-subtitle">请稍候<span class="dots"></span></div>
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
            dispatch({
              type: 'MARK_COMPLETE',
              payload: { messageId: data.message_id }
            })
            setIsTyping(false)
          }
          break

        case 'stopped':
          if (data.type === 'agent_stopped') {
            console.log('Agent execution stopped:', data.message)
            setIsTyping(false)
            // Add a stop message to show the stop
            const stopMessage: Message = {
              id: `${Date.now()}_stopped`,
              type: 'stop' as MessageType,
              content: '执行已停止',
              timestamp: Date.now(),
            }
            dispatch({ type: 'ADD_ERROR', payload: stopMessage })
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
          // Ignore unknown event types
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
        // Stream was aborted (likely due to stop button) - don't change isTyping here
        // Let the 'stopped' event from backend handle it
        console.log('Stream aborted (stop button clicked)')
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

  const stopMessage = useCallback(async () => {
    try {
      // Don't abort stream - let backend finish current work naturally
      
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
      
      // Change UI state immediately - show send button instead of stop button
      setIsTyping(false)
      
      // Backend will naturally finish current work and send "stopped" event
      
    } catch (error: any) {
      console.error('Error stopping message:', error)
      setConnectionError(`Failed to stop: ${error.message}`)
    }
  }, [endpoint, sessionId])

  const retryConnection = useCallback(() => {
    setConnectionError(null)
    setIsConnected(false)
    // For SSE, connection is established per message, so we don't need to do anything here
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
    stopMessage,
    retryConnection,
    setInitialMessages,
  }
}