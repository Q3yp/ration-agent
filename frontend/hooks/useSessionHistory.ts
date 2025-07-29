'use client'

import { useState, useEffect, useCallback } from 'react'
import { SessionHistory, Message, SessionHistoryMessage } from '@/types/chat'

interface UseSessionHistoryProps {
  sessionId: string | null
  endpoint?: string
}

interface UseSessionHistoryReturn {
  sessionHistory: SessionHistory | null
  isLoading: boolean
  error: string | null
  loadSessionHistory: () => Promise<void>
  convertHistoryToMessages: (historyMessages: SessionHistoryMessage[]) => Message[]
}

export function useSessionHistory({ 
  sessionId, 
  endpoint = 'http://localhost:8000' 
}: UseSessionHistoryProps): UseSessionHistoryReturn {
  const [sessionHistory, setSessionHistory] = useState<SessionHistory | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessionHistory = useCallback(async () => {
    if (!sessionId) return

    try {
      setIsLoading(true)
      setError(null)
      
      const response = await fetch(`${endpoint}/sessions/${sessionId}/history?limit=50`)
      
      if (!response.ok) {
        throw new Error(`Failed to load session history: ${response.statusText}`)
      }
      
      const data: SessionHistory = await response.json()
      setSessionHistory(data)
    } catch (error) {
      console.error('Error loading session history:', error)
      setError(error instanceof Error ? error.message : 'Failed to load session history')
      setSessionHistory(null)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, endpoint])

  const convertHistoryToMessages = useCallback((historyMessages: SessionHistoryMessage[]): Message[] => {
    const messages: Message[] = []
    
    historyMessages.forEach((msg, index) => {
      const baseTimestamp = msg.timestamp ? new Date(msg.timestamp).getTime() : Date.now() - (historyMessages.length - index) * 1000
      
      // Handle tool result messages separately
      if (msg.type === 'tool') {
        messages.push({
          id: `history_tool_result_${index}_${Date.now()}`,
          type: 'tool_result',
          content: msg.content,
          timestamp: baseTimestamp,
          isStreaming: false,
          toolCallId: msg.tool_call_id || ''
        })
        return // Don't process further for tool messages
      }
      
      // Add the main message (human, ai, system)
      // Skip AI messages with empty content (they only contain tool calls)
      if (!(msg.type === 'ai' && (!msg.content || msg.content.trim() === ''))) {
        messages.push({
          id: `history_${index}_${Date.now()}`,
          type: msg.type === 'human' ? 'user' : msg.type === 'ai' ? 'agent' : 'system',
          content: msg.content,
          timestamp: baseTimestamp,
          isStreaming: false,
          fullContent: msg.full_content
        })
      }
      
      // Add tool call messages if they exist (for AI messages)
      if (msg.type === 'ai' && msg.tool_calls && msg.tool_calls.length > 0) {
        msg.tool_calls.forEach((toolCall, toolIndex) => {
          // Add tool call message
          messages.push({
            id: `history_tool_call_${index}_${toolIndex}_${Date.now()}`,
            type: 'tool_call',
            content: `Calling ${toolCall.name}...`,
            timestamp: baseTimestamp + toolIndex + 1, // Slight offset to maintain order
            isStreaming: false,
            toolName: toolCall.name,
            toolArgs: toolCall.args,
            toolCallId: toolCall.id
          })
        })
      }
    })
    
    return messages
  }, [])

  useEffect(() => {
    if (sessionId) {
      loadSessionHistory()
    } else {
      setSessionHistory(null)
      setError(null)
    }
  }, [sessionId, loadSessionHistory])

  return {
    sessionHistory,
    isLoading,
    error,
    loadSessionHistory,
    convertHistoryToMessages
  }
}