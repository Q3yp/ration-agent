/**
 * Unified Message Processor
 * 
 * Centralizes all message processing logic for both realtime streaming and history loading.
 * Ensures consistent behavior regardless of message source.
 */

import { Message, MessageType, ArtifactData } from '@/types/chat'

const LOADING_COPY = {
  'zh-CN': {
    title: '正在创建内容...',
    description: '请稍候，正在生成内容中...',
    subtitle: '请稍候...'
  },
  'en-US': {
    title: 'Generating content...',
    description: 'Please wait while we generate your content.',
    subtitle: 'Please wait...'
  }
}

const getLocale = () => {
  if (typeof document === 'undefined') {
    return 'zh-CN'
  }
  return document.documentElement.lang === 'en-US' ? 'en-US' : 'zh-CN'
}

const getLoadingText = () => LOADING_COPY[getLocale() as 'zh-CN' | 'en-US']

export type MessageSource = 'history' | 'sse_stream' | 'user_input'

export type SSEEventType =
  | 'connected'
  | 'message'
  | 'title_update'
  | 'artifact_loading'
  | 'complete'
  | 'stopped'
  | 'error'
  | 'token_usage'
  | 'plan_limit'
  | 'ask_user'

export interface SSEEvent {
  type: SSEEventType
  data: any
}

export interface ProcessedEvent {
  type: 'message' | 'title_update' | 'artifact_update' | 'connection_change' | 'error' | 'token_usage_update' | 'plan_limit' | 'ask_user'
  data: any
}

export interface StreamingUpdate {
  messageId: string
  content: string
  isComplete: boolean
}

export interface MessageProcessorState {
  messages: Message[]
  streamingMessageId: string | null
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'error'
  error: string | null
}

export class MessageProcessor {

  /**
   * Create a normalized Message from any source
   */
  static createMessage(
    data: any,
    source: MessageSource,
    timestamp?: number
  ): Message {
    const now = timestamp || Date.now()

    // If it's already a properly formatted Message, validate and return
    if (MessageProcessor.isValidMessage(data)) {
      return {
        ...data,
        timestamp: data.timestamp || now
      }
    }

    // Handle user input message creation
    if (source === 'user_input') {
      return {
        id: `user_${now}_${Math.random()}`,
        type: 'user' as MessageType,
        content: typeof data === 'string' ? data : data.content || '',
        timestamp: now,
        metadata: data.metadata || undefined
      }
    }

    // Handle backend ParsedMessage format (both history and SSE)
    if (data.id && data.type && data.content !== undefined) {
      return {
        id: data.id,
        type: data.type as MessageType,
        content: data.content,
        timestamp: data.timestamp || now,
        metadata: data.metadata || undefined
      }
    }

    // Fallback for malformed data
    console.warn('MessageProcessor: Received malformed message data:', data)
    return {
      id: `fallback_${now}_${Math.random()}`,
      type: 'agent' as MessageType,
      content: 'Invalid message data received',
      timestamp: now,
      metadata: { error: 'malformed_data', original: data }
    }
  }

  /**
   * Validate that an object is a proper Message
   */
  static isValidMessage(obj: any): obj is Message {
    return obj &&
      typeof obj.id === 'string' &&
      typeof obj.type === 'string' &&
      typeof obj.content === 'string' &&
      typeof obj.timestamp === 'number'
  }

  /**
   * Process SSE events into standardized ProcessedEvents
   */
  static processSSEEvent(eventType: string, eventData: any): ProcessedEvent[] {
    const results: ProcessedEvent[] = []

    try {
      const data = typeof eventData === 'string' ? JSON.parse(eventData) : eventData

      switch (eventType) {
        case 'connected':
          results.push({
            type: 'connection_change',
            data: {
              state: 'connected',
              sessionId: data.session_id,
              messageId: data.message_id,
              mode: data.mode
            }
          })
          break

        case 'message':
          // Backend sends ParsedMessage format in data
          const message = MessageProcessor.createMessage(data, 'sse_stream')
          results.push({
            type: 'message',
            data: message
          })
          break

        case 'title_update':
          if (data.type === 'title_update') {
            results.push({
              type: 'title_update',
              data: {
                sessionId: data.session_id,
                title: data.title
              }
            })
          }
          break

        case 'artifact_loading':
          if (data.type === 'artifact_loading') {
            results.push({
              type: 'artifact_update',
              data: {
                title: getLoadingText().title,
                description: getLoadingText().description,
                html_content: MessageProcessor.createLoadingArtifactHTML(),
                isLoading: true
              }
            })
          }
          break

        case 'complete':
          if (data.type === 'agent_complete') {
            results.push({
              type: 'connection_change',
              data: {
                state: 'connected',
                streamingComplete: true,
                messageId: data.message_id
              }
            })
          }
          break

        case 'stopped':
          if (data.type === 'agent_stopped') {
            results.push({
              type: 'connection_change',
              data: {
                state: 'connected',
                streamingStopped: true,
                message: data.message
              }
            })
          }
          break

        case 'token_usage':
          if (data.type === 'token_usage_update') {
            results.push({
              type: 'token_usage_update',
              data: {
                sessionId: data.session_id,
                tokenUsage: data.token_usage
              }
            })
          }
          break

        case 'plan_limit':
          results.push({
            type: 'plan_limit',
            data
          })
          break

        case 'error':
          results.push({
            type: 'error',
            data: {
              message: data.content || data.message || 'Unknown error occurred',
              details: data
            }
          })
          break

        case 'ask_user':
          results.push({
            type: 'ask_user',
            data: {
              description: data.description || null,
              questions: data.questions || [],
              sessionId: data.session_id,
              timestamp: data.timestamp
            }
          })
          break

        default:
          console.warn(`MessageProcessor: Unknown SSE event type: ${eventType}`)
      }
    } catch (error) {
      console.error('MessageProcessor: Error processing SSE event:', error)
      results.push({
        type: 'error',
        data: {
          message: 'Failed to process server event',
          details: { eventType, eventData, error: error instanceof Error ? error.message : String(error) }
        }
      })
    }

    return results
  }

  /**
   * Handle streaming message updates with accumulation
   */
  static processStreamingMessage(
    currentMessages: Message[],
    newMessage: Message
  ): Message[] {
    // If it's a streaming agent message, handle accumulation
    if (newMessage.type === 'agent' && newMessage.metadata?.is_streaming) {
      const existingIndex = currentMessages.findIndex(msg => msg.id === newMessage.id)

      if (existingIndex >= 0) {
        // Accumulate content for existing message
        const updated = [...currentMessages]
        updated[existingIndex] = {
          ...updated[existingIndex],
          content: updated[existingIndex].content + newMessage.content,
          timestamp: newMessage.timestamp,
          metadata: newMessage.metadata
        }
        return updated
      } else {
        // New streaming message
        return [...currentMessages, newMessage]
      }
    } else {
      // Non-streaming message - add directly
      return [...currentMessages, newMessage]
    }
  }

  /**
   * Mark streaming message as complete
   */
  static completeStreamingMessage(
    currentMessages: Message[],
    messageId: string
  ): Message[] {
    return currentMessages.map(msg =>
      msg.id === messageId
        ? { ...msg, metadata: { ...msg.metadata, is_streaming: false } }
        : msg
    )
  }

  /**
   * Extract artifact data from message for display
   */
  static extractArtifactData(message: Message): ArtifactData | null {
    if (message.type !== 'artifact' || !message.metadata) {
      return null
    }

    return {
      title: message.metadata.title || message.content,
      description: message.metadata.description || '',
      html_content: message.metadata.html_content || '',
      isLoading: message.metadata.isLoading || false
    }
  }

  /**
   * Process array of messages from history API
   */
  static processHistoryMessages(historyData: any[]): Message[] {
    if (!Array.isArray(historyData)) {
      console.warn('MessageProcessor: History data is not an array:', historyData)
      return []
    }

    // Normalize, validate and sort
    const normalized = historyData
      .map(data => MessageProcessor.createMessage(data, 'history'))
      .filter(msg => MessageProcessor.isValidMessage(msg))
      .sort((a, b) => a.timestamp - b.timestamp)

    // Ensure IDs are unique within history to avoid collapsing multiple
    // events that may share the same backend id (e.g., analysis/formulation completes)
    const idCounts = new Map<string, number>()
    const withUniqueIds = normalized.map((msg) => {
      const seenCount = idCounts.get(msg.id) || 0
      idCounts.set(msg.id, seenCount + 1)
      if (seenCount === 0) return msg
      // Suffix duplicates deterministically while preserving order
      return { ...msg, id: `${msg.id}__dup_${seenCount + 1}` }
    })

    return withUniqueIds
  }

  /**
   * Deduplicate messages by ID while preserving order
   */
  static deduplicateMessages(messages: Message[]): Message[] {
    const seen = new Set<string>()
    return messages.filter(msg => {
      if (seen.has(msg.id)) {
        return false
      }
      seen.add(msg.id)
      return true
    })
  }

  /**
   * Validate message state integrity
   */
  static validateMessageState(state: MessageProcessorState): boolean {
    // Check that all messages are valid
    const allValid = state.messages.every(msg => MessageProcessor.isValidMessage(msg))

    // Check that streaming message ID exists if set
    const streamingValid = !state.streamingMessageId ||
      state.messages.some(msg => msg.id === state.streamingMessageId)

    return allValid && streamingValid
  }

  /**
   * Create loading artifact HTML content
   */
  private static createLoadingArtifactHTML(): string {
    const copy = getLoadingText()
    const locale = getLocale()
    return `
      <!DOCTYPE html>
      <html lang="${locale}">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>${copy.title}</title>
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
            <div class="loading-text">${copy.title}</div>
            <div class="loading-subtitle">${copy.subtitle}</div>
          </div>
        </body>
      </html>
    `
  }
}
