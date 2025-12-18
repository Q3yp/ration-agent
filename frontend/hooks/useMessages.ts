'use client'

/**
 * Unified Messages Hook
 * 
 * Replaces useSSEChat and useSessionHistory with a single, consistent interface.
 * Handles both history loading and realtime streaming with unified processing.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Message, AttachedFile, ArtifactData } from '@/types/chat'
import {
  MessageProcessor,
  MessageProcessorState,
  ProcessedEvent
} from '@/utils/messageProcessor'
import { ErrorHandler } from '@/utils/errorHandler'
import { getAuthHeadersWithDefaults } from '@/utils/authHeaders'
import { useI18n } from '@/contexts/I18nContext'

interface UseMessagesConfig {
  sessionId: string
  endpoint?: string
  autoLoadHistory?: boolean
  onTitleUpdate?: (sessionId: string, title: string) => void
  onArtifactUpdate?: (artifactData: ArtifactData | null) => void
  onConnectionChange?: (connected: boolean) => void
  onError?: (error: string) => void
  onTokenUsageUpdate?: (sessionId: string, tokenUsage: import('@/types/chat').TokenUsage) => void
}

interface AnalysisState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
  operations?: string[]  // Track all operations for rotary effect
}

interface FormulationState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
  operations?: string[]
  operationData?: any[]  // Track structured data for each operation
}

interface ThinkingState {
  isActive: boolean
  content: string
  isComplete: boolean
}

interface PlanLimitInfo {
  sessionId: string
  limit: number
  tier?: string
  promptTokens?: number
}

interface AskUserState {
  isActive: boolean
  description?: string | null
  questions: string[]
}

interface UseMessagesReturn {
  // Core state
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  isConnected: boolean
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'error'
  error: string | null
  isTyping: boolean  // Immediate typing state for responsive UX
  analysisState?: AnalysisState
  formulationState?: FormulationState
  thinkingState?: ThinkingState  // DeepSeek reasoning content state
  planLimitInfo: PlanLimitInfo | null
  askUserState?: AskUserState  // Ask user for more info state

  // Actions
  sendMessage: (message: string, filesToShow?: AttachedFile[]) => Promise<void>
  stopMessage: () => Promise<void>
  resumeChat: (response: string) => Promise<void>  // Resume after ask_user
  loadHistory: () => Promise<void>
  retryConnection: () => void
  clearError: () => void
  clearPlanLimitInfo: () => void

  // State management
  addMessage: (message: Message) => void
  setInitialMessages: (messages: Message[]) => void
}

export function useMessages(config: UseMessagesConfig): UseMessagesReturn {
  const {
    sessionId,
    endpoint = '/api',
    autoLoadHistory = true,
    onTitleUpdate,
    onArtifactUpdate,
    onConnectionChange,
    onError,
    onTokenUsageUpdate
  } = config

  const { t } = useI18n()

  // Core state using MessageProcessor state structure
  const [state, setState] = useState<MessageProcessorState>({
    messages: [],
    streamingMessageId: null,
    connectionState: 'disconnected',
    error: null
  })

  const [isLoading, setIsLoading] = useState(false)
  const [isTyping, setIsTyping] = useState(false)  // Immediate typing feedback
  const [analysisState, setAnalysisState] = useState<AnalysisState | undefined>(undefined)
  const [formulationState, setFormulationState] = useState<FormulationState | undefined>(undefined)
  const [thinkingState, setThinkingState] = useState<ThinkingState | undefined>(undefined)
  const [planLimitInfo, setPlanLimitInfo] = useState<PlanLimitInfo | null>(null)
  const [askUserState, setAskUserState] = useState<AskUserState | undefined>(undefined)
  const abortControllerRef = useRef<AbortController | null>(null)
  const historyLoadedRef = useRef(false)
  const resumeStartedRef = useRef(false)

  useEffect(() => {
    setPlanLimitInfo(null)
  }, [sessionId])

  const clearPlanLimitInfo = useCallback(() => {
    setPlanLimitInfo(null)
  }, [])

  // Derived state
  const isStreaming = useMemo(() => state.streamingMessageId !== null, [state.streamingMessageId])
  const isConnected = useMemo(() => state.connectionState === 'connected', [state.connectionState])

  /**
   * Update state with validation - supports both object updates and functional updates
   */
  const updateState = useCallback((updates: Partial<MessageProcessorState> | ((prevState: MessageProcessorState) => Partial<MessageProcessorState>)) => {
    setState(prevState => {
      const updateObj = typeof updates === 'function' ? updates(prevState) : updates
      const newState = { ...prevState, ...updateObj }

      // Validate state integrity
      if (!MessageProcessor.validateMessageState(newState)) {
        console.warn('MessageProcessor: Invalid state update attempted', { prevState, updateObj, newState })
        return prevState
      }

      return newState
    })
  }, [])

  /**
   * Process events from any source
   */
  const processEvents = useCallback((events: ProcessedEvent[]) => {
    for (const event of events) {
      switch (event.type) {
        case 'message':
          const message = event.data as Message

          // Handle analysis events
          if (message.type === 'analysis_start' || message.type === 'analysis_update' || message.type === 'analysis_complete') {
            if (message.type === 'analysis_start') {
              setAnalysisState({
                isActive: true,
                content: message.content,
                isComplete: false,
                operations: [message.content]  // Start with initialization message
              })
              // Stop typing when analysis starts
              if (isTyping) {
                setIsTyping(false)
              }
              // Don't add start events as regular messages
              break
            } else if (message.type === 'analysis_update') {
              // Use the individual operation from metadata, or fall back to content
              const operation = message.metadata?.operation || message.content
              setAnalysisState(prev => {
                if (!prev) {
                  // Resume scenario: create state from update event
                  return {
                    isActive: true,
                    content: message.content,
                    isComplete: false,
                    operations: [operation]
                  }
                }
                const currentOperations = prev.operations || []
                return {
                  ...prev,
                  content: message.content,
                  operations: [...currentOperations, operation]
                }
              })
              // Don't add update events as regular messages
              break
            } else if (message.type === 'analysis_complete') {
              // Immediately clear analysis state - completion creates permanent message
              setAnalysisState(undefined)

              // Let analysis_complete create a permanent message - don't break
            }
          }

          // Handle formulation events
          if (message.type === 'formulation_start' || message.type === 'formulation_update' || message.type === 'formulation_complete') {
            if (message.type === 'formulation_start') {
              setFormulationState({
                isActive: true,
                content: message.content,
                isComplete: false,
                operations: [message.content],
                operationData: []
              })
              // Stop typing when formulation starts
              if (isTyping) {
                setIsTyping(false)
              }
              // Don't add start events as regular messages
              break
            } else if (message.type === 'formulation_update') {
              // Use the individual operation from metadata, or fall back to content
              const operation = message.metadata?.operation || message.content
              const operationData = message.metadata?.operation_data
              setFormulationState(prev => {
                if (!prev) {
                  // Resume scenario: create state from update event
                  return {
                    isActive: true,
                    content: message.content,
                    isComplete: false,
                    operations: [operation],
                    operationData: operationData ? [operationData] : []
                  }
                }
                const currentOperations = prev.operations || []
                const currentOperationData = prev.operationData || []
                return {
                  ...prev,
                  content: message.content,
                  operations: [...currentOperations, operation],
                  operationData: [...currentOperationData, operationData]
                }
              })
              // Stop typing when formulation updates
              if (isTyping) {
                setIsTyping(false)
              }
              // Don't add update events as regular messages
              break
            } else if (message.type === 'formulation_complete') {
              // Immediately clear formulation state - completion creates permanent message
              setFormulationState(undefined)

              // Let formulation_complete create a permanent message - don't break
            }
          }

          // Handle thinking messages (DeepSeek reasoning content)
          if (message.type === 'thinking') {
            // Accumulate thinking content in real-time
            setThinkingState(prev => {
              if (!prev) {
                // Start new thinking
                return {
                  isActive: true,
                  content: message.content,
                  isComplete: false
                }
              }
              // Append to existing thinking (streaming)
              return {
                ...prev,
                content: prev.content + message.content
              }
            })
            // Stop regular typing indicator when thinking starts
            if (isTyping) {
              setIsTyping(false)
            }
            // Break out of switch - thinking messages are shown in indicator only
            break
          }

          // When regular agent content arrives, clear thinking state (reasoning is done)
          if (message.type === 'agent' && !message.metadata?.is_thinking) {
            if (thinkingState?.isActive) {
              // Mark thinking as complete before clearing
              setThinkingState(prev => prev ? { ...prev, isActive: false, isComplete: true } : undefined)
              // Clear after short delay to allow collapse animation
              setTimeout(() => setThinkingState(undefined), 1500)
            }
          }

          // Use functional update to ensure we have the latest messages
          updateState(prevState => ({
            messages: MessageProcessor.processStreamingMessage(prevState.messages, message),
            streamingMessageId: message.metadata?.is_streaming ? message.id : prevState.streamingMessageId
          }))

          // Stop typing when first non-analysis message arrives
          if (isTyping) {
            setIsTyping(false)
          }

          // Clear analysis state when regular agent messages arrive (analysis is done)
          if (message.type === 'agent' && analysisState?.isComplete) {
            // Set a timeout to clear analysis state after completion state is seen
            setTimeout(() => {
              setAnalysisState(undefined)
            }, 2000)  // Longer delay to let users see the completion
          }

          // Handle artifact messages
          if (message.type === 'artifact' && onArtifactUpdate) {
            const artifactData = MessageProcessor.extractArtifactData(message)
            if (artifactData) {
              onArtifactUpdate(artifactData)
            }
          }
          break

        case 'title_update':
          if (onTitleUpdate) {
            onTitleUpdate(event.data.sessionId, event.data.title)
          }
          break

        case 'artifact_update':
          if (onArtifactUpdate) {
            onArtifactUpdate(event.data as ArtifactData)
          }
          break

        case 'connection_change':
          const connData = event.data

          if (connData.streamingComplete || connData.streamingStopped) {
            // Complete streaming message using functional update
            updateState(prevState => {
              const completedMessages = prevState.streamingMessageId
                ? MessageProcessor.completeStreamingMessage(prevState.messages, prevState.streamingMessageId)
                : prevState.messages

              return {
                messages: completedMessages,
                streamingMessageId: null,
                connectionState: connData.state || prevState.connectionState
              }
            })
            setIsTyping(false)  // Ensure typing is false when complete
            return
          }

          if (connData.state) {
            updateState({
              connectionState: connData.state
            })
            // On reconnect to a live stream, show typing immediately until first event clears it
            if (connData.state === 'connected' && connData.mode === 'stream') {
              setIsTyping(true)
            }
          }

          if (onConnectionChange && connData.state) {
            onConnectionChange(connData.state === 'connected')
          }
          break

        case 'token_usage_update':
          if (onTokenUsageUpdate) {
            onTokenUsageUpdate(event.data.sessionId, event.data.tokenUsage)
          }
          break

        case 'plan_limit':
          setPlanLimitInfo({
            sessionId: event.data.session_id,
            limit: event.data.limit,
            tier: event.data.tier,
            promptTokens: event.data.prompt_tokens,
          })
          setIsTyping(false)
          updateState(prev => ({
            ...prev,
            streamingMessageId: null,
            connectionState: 'connected'
          }))
          break

        case 'error':
          const rawError = event.data
          const classified = ErrorHandler.classify({
            message: rawError.message || rawError.content || 'Server error',
            ...rawError
          })

          updateState({
            error: classified.userMessage,
            connectionState: 'error',
            streamingMessageId: null
          })

          setIsTyping(false)  // Stop typing on error

          if (onError) {
            onError(classified.userMessage)
          }

          // Auto-retry for certain error types
          if (ErrorHandler.shouldAutoRetry(classified.originalError)) {
            setTimeout(() => {
              console.log('Auto-retrying after error...')
              retryConnection()
            }, 3000)
          }
          break

        case 'ask_user':
          // Agent is requesting more information from user
          setAskUserState({
            isActive: true,
            description: event.data.description || null,
            questions: event.data.questions || []
          })
          setIsTyping(false)
          break
      }
    }
  }, [updateState, onTitleUpdate, onArtifactUpdate, onConnectionChange, onError, onTokenUsageUpdate, state, analysisState, thinkingState, isTyping])

  /**
   * Load session history
   */
  const loadHistory = useCallback(async () => {
    if (!sessionId || historyLoadedRef.current) {
      return
    }

    try {
      setIsLoading(true)
      updateState({ error: null })

      const response = await fetch(`${endpoint}/sessions/${sessionId}/history`, {
        headers: getAuthHeadersWithDefaults()
      })

      if (!response.ok) {
        throw new Error(`Failed to load session history: ${response.statusText}`)
      }

      const data = await response.json()
      const messages = MessageProcessor.processHistoryMessages(data.messages || [])

      updateState({
        messages: MessageProcessor.deduplicateMessages(messages),
        connectionState: 'connected'
      })

      historyLoadedRef.current = true
    } catch (error) {
      ErrorHandler.logError(error, 'loadHistory')
      const classified = ErrorHandler.classify(error)
      updateState({
        error: classified.userMessage,
        connectionState: 'error'
      })

      if (onError) {
        onError(classified.userMessage)
      }
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, endpoint, updateState])

  /**
   * Start history stream: stream persisted history, then if live, tail new events until complete
   */
  const startHistoryStream = useCallback(async () => {
    if (!sessionId) return
    try {
      // Abort any previous stream
      if (abortControllerRef.current) {
        try { abortControllerRef.current.abort() } catch { }
        abortControllerRef.current = null
      }
      abortControllerRef.current = new AbortController()

      updateState({ error: null, connectionState: 'connecting' })

      const response = await fetch(`${endpoint}/sessions/${sessionId}/history`, {
        method: 'GET',
        headers: getAuthHeadersWithDefaults({ 'Accept': 'text/event-stream' }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`History stream failed: HTTP ${response.status}`)
      }
      if (!response.body) {
        throw new Error('No response body for history stream')
      }

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
              const events = MessageProcessor.processSSEEvent(eventType, eventData)
              processEvents(events)
              eventType = 'message'
              eventData = ''
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    } catch (error: any) {
      if (error?.name === 'AbortError') return
      ErrorHandler.logError(error, 'startHistoryStream')
      const classified = ErrorHandler.classify(error)
      updateState({ error: classified.userMessage, connectionState: 'error' })
      if (onError) onError(classified.userMessage)
      // Fallback: try to show JSON history
      try {
        if (autoLoadHistory) {
          historyLoadedRef.current = false
          await loadHistory()
        }
      } catch { }
    }
  }, [sessionId, endpoint, updateState, processEvents, onError, autoLoadHistory, loadHistory])

  /**
   * Send message with SSE streaming
   */
  const sendMessage = useCallback(async (message: string, filesToShow?: AttachedFile[]) => {
    if (!message.trim() || !sessionId) {
      return
    }

    try {
      // Add user message immediately
      const userMessage = MessageProcessor.createMessage({
        content: message.trim(),
        metadata: { attached_files: filesToShow }
      }, 'user_input')

      updateState(prevState => ({
        messages: [...prevState.messages, userMessage],
        error: null,
        connectionState: 'connecting'
      }))

      // Set typing immediately for responsive UX
      setIsTyping(true)
      // Mark previous states as stopped instead of clearing them
      // This preserves the status blocks for user visibility
      setAnalysisState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)
      setFormulationState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)
      setThinkingState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController()

      // Send message to SSE endpoint
      const response = await fetch(`${endpoint}/chat/stream/${sessionId}`, {
        method: 'POST',
        headers: getAuthHeadersWithDefaults({
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        }),
        body: JSON.stringify({ message: message.trim() }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('No response body for streaming')
      }

      // Process SSE stream
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
              const events = MessageProcessor.processSSEEvent(eventType, eventData)
              processEvents(events)
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

      ErrorHandler.logError(error, 'sendMessage')
      const classified = ErrorHandler.classify(error)
      updateState({
        error: classified.userMessage,
        connectionState: 'error',
        streamingMessageId: null
      })

      setIsTyping(false)  // Stop typing on error

      if (onError) {
        onError(classified.userMessage)
      }
    }
  }, [sessionId, endpoint, updateState, processEvents])

  /**
   * Stop current message streaming
   */
  const stopMessage = useCallback(async () => {
    try {
      // Abort current request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }

      // Send stop request to backend
      const response = await fetch(`${endpoint}/chat/stop/${sessionId}`, {
        method: 'POST',
        headers: getAuthHeadersWithDefaults({
          'Content-Type': 'application/json',
        }),
      })

      if (!response.ok) {
        throw new Error(`Failed to stop: ${response.statusText}`)
      }

      const result = await response.json()
      console.log('Stop requested:', result.message)

      updateState({
        streamingMessageId: null,
        connectionState: 'connected'
      })

      setIsTyping(false)  // Stop typing when stopped
      // Mark states as stopped to preserve visibility
      setAnalysisState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)
      setFormulationState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)
      setThinkingState(prev => prev?.isActive ? { ...prev, isActive: false, isComplete: true } : prev)

    } catch (error: any) {
      ErrorHandler.logError(error, 'stopMessage')
      const classified = ErrorHandler.classify(error)
      updateState({
        error: classified.userMessage,
        connectionState: 'error'
      })

      setIsTyping(false)  // Stop typing on error

      if (onError) {
        onError(classified.userMessage)
      }
    }
  }, [endpoint, sessionId, updateState])

  /**
   * Resume chat after ask_user interrupt with user's response
   */
  const resumeChat = useCallback(async (response: string) => {
    if (!response.trim() || !sessionId) {
      return
    }

    try {
      // Clear ask user state
      setAskUserState(undefined)
      setIsTyping(true)

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController()

      // Send response to resume endpoint
      const fetchResponse = await fetch(`${endpoint}/chat/resume/${sessionId}`, {
        method: 'POST',
        headers: getAuthHeadersWithDefaults({
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        }),
        body: JSON.stringify({ response: response.trim() }),
        signal: abortControllerRef.current.signal,
      })

      if (!fetchResponse.ok) {
        throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`)
      }

      if (!fetchResponse.body) {
        throw new Error('No response body for streaming')
      }

      // Process SSE stream (same as sendMessage)
      const reader = fetchResponse.body.getReader()
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
              const events = MessageProcessor.processSSEEvent(eventType, eventData)
              processEvents(events)
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
        console.log('Resume stream aborted')
        return
      }

      ErrorHandler.logError(error, 'resumeChat')
      const classified = ErrorHandler.classify(error)
      updateState({
        error: classified.userMessage,
        connectionState: 'error',
        streamingMessageId: null
      })

      setIsTyping(false)
      setAskUserState(undefined)

      if (onError) {
        onError(classified.userMessage)
      }
    }
  }, [sessionId, endpoint, updateState, processEvents])

  /**
   * Retry connection after error with intelligent retry logic
   */
  const retryConnection = useCallback(() => {
    updateState({
      error: null,
      connectionState: 'connecting'
    })

    // Create retry function with exponential backoff for network errors
    const retryFn = ErrorHandler.createRetryFunction(
      async () => {
        if (autoLoadHistory) {
          historyLoadedRef.current = false
          await loadHistory()
        }
      },
      {
        maxRetries: 3,
        retryDelay: 1000,
        exponentialBackoff: true,
        onRetry: () => {
          console.log('Retrying connection...')
        },
        onMaxRetriesReached: () => {
          updateState({
            error: t('errors.networkRetry'),
            connectionState: 'error'
          })
        }
      }
    )

    retryFn().catch(error => {
      ErrorHandler.logError(error, 'retryConnection')
      const classified = ErrorHandler.classify(error)
      updateState({
        error: classified.userMessage,
        connectionState: 'error'
      })
    })
  }, [updateState, autoLoadHistory, loadHistory])

  /**
   * Clear current error
   */
  const clearError = useCallback(() => {
    updateState({ error: null })
  }, [updateState])

  /**
   * Add a message manually
   */
  const addMessage = useCallback((message: Message) => {
    updateState(prevState => ({
      messages: [...prevState.messages, message]
    }))
  }, [updateState])

  /**
   * Set initial messages (for migration from old hooks)
   */
  const setInitialMessages = useCallback((messages: Message[]) => {
    updateState({
      messages: MessageProcessor.deduplicateMessages(messages),
      streamingMessageId: null
    })
  }, [updateState])

  /**
   * Auto-load history when session changes
   */
  useEffect(() => {
    if (!sessionId || !autoLoadHistory) return
    if (!resumeStartedRef.current) {
      resumeStartedRef.current = true
      // Single, unified history stream: replays history and, if active, tails live events
      startHistoryStream()
    }
  }, [sessionId, autoLoadHistory])

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        try {
          abortControllerRef.current.abort()
        } catch (error) {
          // Ignore cleanup errors
        }
        abortControllerRef.current = null
      }
    }
  }, [])

  /**
   * Reset state when session changes
   */
  useEffect(() => {
    updateState({
      messages: [],
      streamingMessageId: null,
      connectionState: 'disconnected',
      error: null
    })
    setIsTyping(false)
    setAnalysisState(undefined)
    setFormulationState(undefined)
    setThinkingState(undefined)  // Clear thinking state on session change
    historyLoadedRef.current = false
    resumeStartedRef.current = false
  }, [sessionId, updateState])

  return {
    // Core state
    messages: state.messages,
    isLoading,
    isStreaming,
    isConnected,
    connectionState: state.connectionState,
    error: state.error,
    isTyping,  // Immediate responsive typing state
    analysisState,
    formulationState,
    thinkingState,  // DeepSeek reasoning content state
    planLimitInfo,
    askUserState,  // Ask user for more info state

    // Actions
    sendMessage,
    stopMessage,
    resumeChat,
    loadHistory,
    retryConnection,
    clearError,
    clearPlanLimitInfo,

    // State management
    addMessage,
    setInitialMessages
  }
}
