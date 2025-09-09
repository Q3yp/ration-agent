'use client'

import { useState, useEffect, useCallback } from 'react'
import { Message } from '@/types/chat'
import { httpClient } from '@/utils/httpClient'

interface UseSessionHistoryProps {
  sessionId: string | null
}

interface SessionHistoryResponse {
  session_id: string
  messages: Message[]  // Already in unified ParsedMessage format from backend
  summary: {
    session_id: string
    total_messages: number
    human_messages: number
    ai_messages: number
    system_messages: number
    has_history: boolean
  }
}

interface UseSessionHistoryReturn {
  messages: Message[]
  isLoading: boolean
  error: string | null
  loadSessionHistory: () => Promise<void>
}

export function useSessionHistory({ 
  sessionId
}: UseSessionHistoryProps): UseSessionHistoryReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessionHistory = useCallback(async () => {
    if (!sessionId) {
      setMessages([])
      setError(null)
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      
      const data: SessionHistoryResponse = await httpClient.getJson(`/sessions/${sessionId}/history`)
      
      // Backend now returns ParsedMessage format directly with proper metadata
      setMessages(data.messages || [])
    } catch (error) {
      console.error('Error loading session history:', error)
      setError(error instanceof Error ? error.message : 'Failed to load session history')
      setMessages([])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    loadSessionHistory()
  }, [loadSessionHistory])

  return {
    messages,
    isLoading,
    error,
    loadSessionHistory
  }
}